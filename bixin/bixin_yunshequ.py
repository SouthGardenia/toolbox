import asyncio
import hashlib
import json
import os
import sys
import random
import time

import requests
import websockets

sys.path.append(os.path.dirname(sys.path[0]))
from util import DingBot

CORP_ID = os.getenv('CORP_ID')
DING_BOT_URL = os.getenv("DING_BOT_URL")
Y_HOST = os.getenv("Y_HOST")
DING_CONSOLE_ID = os.getenv("DING_CONSOLE_ID")
if not all([CORP_ID, DING_BOT_URL, Y_HOST, DING_CONSOLE_ID]):
    raise EnvironmentError('参数[CORP_ID, DING_BOT_URL, Y_HOST, DING_CONSOLE_ID]未完全配置，请检查secrets！')


class Config:
    def __init__(self, corp_id, y_host, ding_console_id, ding_bot_url):
        self.corpId = corp_id
        self.y_host = y_host
        self.ding_console_id = ding_console_id
        self.ding_bot_url = ding_bot_url

        self.max_like_cnt_per_day = 0
        self.max_comment_cnt_per_day = 0
        self.auth_code_retry_cnt = 3

        # ding
        self.ding_auth_code = ''
        self.ding_wss_url = f'wss://ding-doc.dingtalk.com/ws/console/{ding_console_id}'
        self.ding_confirm_wss_url = f'https://open-dev.dingtalk.com/terminal.html?console_id={ding_console_id}'

        self.ding_auth_code_body = {
            'event': 'JSAPI_INVOKE',
            'msgBody': {
                'apiCategory': {
                    'children': [{
                        'id': 2827,
                        'name': '免登',
                        'parentId': 2800,
                        'prevId': 2802}],
                    'id': 2800,
                    'name': 'JSAPI',
                    'parentId': 0,
                    'prevId': 4600
                },
                'apType': 'H5',
                'desc': '获取微应用免登授权码',
                'docUrl': 'https://developers.dingtalk.com/document/app/obtain-the-micro-application-logon-free-authorization-code',
                'explorerStatus': 1,
                'icmsId': 2732451,
                'name': '获取微应用免登授权码',
                'params': [{
                    'desc': '企业ID',
                    'name': 'corpId',
                    'required': True,
                    'type': 'String',
                    'value': self.corpId}],
                'platform': ['android', 'ios'],
                'status': 'FULLY_OPEN',
                'tags': [],
                'uuid': 'runtime.permission.requestAuthCode'
            }
        }

        # 云社区配置
        self.y_domain = f'https://{y_host}'
        self.login_url = f'{self.y_domain}/community/user/login'
        self.rank_url = f'{self.y_domain}/community/staffIntegral/totalScoreRank?pageNo=1&pageSize=100&__platform=pc&versionNumber=3'
        self.comment_list_url = f'{self.y_domain}/community/comment/list'
        self.comment_publish_url = f'{self.y_domain}/community/comment/publish'
        self.comment_like_url = f'{self.y_domain}/community/comment/like'
        self.feed_like_url = f'{self.y_domain}/community/feed/like'
        self.feed_list_url = f'{self.y_domain}/community/feed/list?sortType=0&topicId=33779&category=1&offset=0&pageNo=1&pageSize=100&isNeedTopList=true&__platform=pc&versionNumber=3'
        self.comment_words = ['超赞～', '不错__', '哇~']


session = requests.session()
conf = Config(corp_id=CORP_ID, y_host=Y_HOST, ding_console_id=DING_CONSOLE_ID, ding_bot_url=DING_BOT_URL)
headers = {
    'Host': conf.y_host,
    'accept': 'application/json, text/plain, */*',
    'origin': conf.y_domain,
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36 DingTalk(5.1.1-macOS-1697) nw',
    'accept-language': 'zh-CN,zh;q=0.9',
}
bot = DingBot.DingBot(webhook=conf.ding_bot_url)


async def get_code():
    async with websockets.connect(conf.ding_wss_url) as wss:
        if wss.open:
            print("wss开流成功! 请点击钉钉链接")
            send_ding_msg()
        else:
            print('wss开流失败')
            return
        resp = await wss.recv()
        print(f"wss<<<< {resp}")
        await wss.send(json.dumps(conf.ding_auth_code_body))
        resp = await wss.recv()

        code = json.loads(json.loads(resp)['jsApiDetail']['result'])['result']['code']
        print(f"wss<<<< {resp}")
        print(f"=== authCode: {code} ===")
        conf.ding_auth_code = code


def get_ding_talk_auth_code():
    asyncio.get_event_loop().run_until_complete(get_code())


def login():
    # 2积分/天
    payload = {
        'authCode': conf.ding_auth_code,
        'corpId': conf.corpId,
        '__platform': 'pc',
        'versionNumber': '3'
    }
    response = session.post(conf.login_url, headers=headers, data=payload)
    print(f'云社区登录：{response.text}')
    ensure200(response)

    user_info = response.json()['result']
    # 用户已登录
    custom_name = response.headers.get('customname')
    token = response.headers.get('token')
    print(f'customname: {custom_name}, token: {token}')
    headers.update({
        'customname': custom_name,
        'token': token
    })
    return user_info


def list_article() -> []:
    response = session.get(conf.feed_list_url, headers=headers)
    ensure200(response)
    arts = response.json()['result']['list']
    print(f'获取到文章数: {len(arts)}')
    return arts


def list_un_like_article(articles):
    ret = []
    for art in articles:
        if not art['like']:
            ret.append(art)

    print(f'未点赞文章: {len(ret)}/{len(articles)}篇')
    return ret


def list_un_like_comments(article):
    params = {
        'pageNo': 1,
        'pageSize': 100,
        'orderType': 0,
        'feedId': article['id'],
        'sign': get_sign(article['id']),
        '__platform': 'pc',
        'versionNumber': 3
    }
    response = session.get(conf.comment_list_url, headers=headers, params=params)
    ensure200(response)
    comments = response.json()['result']['list'] or []
    title = article.get("title") or article.get("content")

    ret = []
    for comment in comments:
        if not comment['like']:
            ret.append(comment)

    print(f'获取评论, 帖子: <{title}>, 评论数: {len(comments)}, 未点赞评论数: {len(ret)}')
    return ret


def do_feed_like(un_like_articles, limit):
    for i in range(limit, 0, -1):
        art = un_like_articles[i - 1]
        payload = {
            'feedId': art['id'],
            'isLike': 'true',
            'sign': get_sign(art["id"]),
            '__platform': 'pc',
            'versionNumber': '3'
        }
        response = session.post(conf.feed_like_url, headers=headers, data=payload)
        ensure200(response)
        r = response.json()
        if r['code'] == 200:
            print(f'点赞成功:《{art.get("title") or art.get("content")}》---{art["user"]["nickname"]}')
        else:
            print(f'点赞失败: {r["message"]}')

    print(f'点赞完毕: {limit}/{len(un_like_articles)}条')


def do_like(articles, like_limit_cnt):
    result = []
    un_like_art = list_un_like_article(articles)
    if len(un_like_art) >= like_limit_cnt:
        do_feed_like(un_like_art, like_limit_cnt)
    else:
        done_cnt = 0
        idx = 0
        while done_cnt < like_limit_cnt:
            art = articles[idx]
            un_like_cms = list_un_like_comments(art)
            do_comment_like(art, un_like_cms, like_limit_cnt - done_cnt)
            done_cnt += len(un_like_cms)
            idx += 1


def do_comment_like(article, un_like_comments, limit):
    # 随机点赞
    payload = {
        'isLike': 'true',
        '__platform': 'pc',
        'versionNumber': '3',
    }

    title = article.get("title") or article.get("content")

    commented_cnt = 0
    for comment in un_like_comments:
        payload.update({
            'commentId': comment['id'],
            'sign': get_sign(comment['id'])
        })
        response = session.post(conf.comment_like_url, headers=headers, data=payload)
        ensure200(response)
        r = response.json()
        if r['code'] == 200:
            print(f'点赞成功：《{title}》\t「{comment["content"]}」---{comment["commentUser"]["nickname"]}')
            commented_cnt += 1
        else:
            print(f'点赞失败: {r["message"]}')

        if commented_cnt >= limit:
            break


def do_comment(articles, limit):
    # 随机评论
    payload = {
        "isAnonymity": 1,
        "users": "[]",
        "__platform": "pc",
        "versionNumber": 3
    }

    for cnt in range(limit):
        art_idx = int(random.random() * len(articles))
        art = articles[art_idx]
        art_id = art['id']
        sign = get_sign(art_id)

        cmt_word = conf.comment_words[cnt % len(conf.comment_words)]
        data = {
            "content": cmt_word,
            "feedId": art_id,
            "sign": sign,
        }
        data.update(payload)

        inner_headers = {'sign': sign}
        inner_headers.update(headers)

        response = session.post(conf.comment_publish_url, headers=inner_headers, json=data)
        ensure200(response)
        headers.update({'token': response.headers.get('token')})
        print(f'评论成功:《{art.get("title") or art.get("content")}》---{art["user"]["nickname"]} 📢{cmt_word}')
        time.sleep(int(5 + random.random() * 10))


def show_rank(user):
    response = session.get(conf.rank_url, headers=headers)
    ensure200(response)
    rank_list = response.json()['result']['list']
    for i in range(len(rank_list)):
        cur = rank_list[i]
        print(f'rank: {i + 1},\t姓名: {cur["userName"]},\t分数: {cur["totalScore"]},\t本月变化: {cur["changeScore"]:+}')
        if cur['userId'] == user['userId']:
            print(f'您的当前排名: {i + 1}名')
            return
    print(f'您的排名: 100+')


def do_daily_job():
    # 登录 2积分/天
    user_info = login()
    print(user_info)
    articles = list_article()
    # 点赞 2积分/条 3条/天
    do_like(articles, conf.max_like_cnt_per_day)
    # 评论 2积分/条 3条/天
    do_comment(articles, conf.max_comment_cnt_per_day)
    # 排名展示
    show_rank(user_info)
    # 完成提示


def ensure200(resp):
    if resp.status_code != 200:
        raise ConnectionError(f'接口异常, resp: {resp.text}')


def get_sign(art_id):
    return hashlib.md5((str(art_id) + 'sq2019').encode()).hexdigest()


def send_ding_msg():
    text = f"#### 自动逛云社区, [赚经验请点我]({conf.ding_confirm_wss_url})"
    bot.send_markdown('点击赚取云社区积分', text)


if __name__ == '__main__':
    for nonce in range(conf.auth_code_retry_cnt, 0, -1):
        # 获取设置 Config.ding_auth_code
        get_ding_talk_auth_code()
        if conf.ding_auth_code:
            break
    if not conf.ding_auth_code:
        msg = '未能获取到dingTalk的authCode，请手动检查'
        print(msg)
    do_daily_job()
