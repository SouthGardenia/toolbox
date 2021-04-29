import requests


def is_not_null_and_blank_str(content):
    if content and content.strip():
        return True
    else:
        return False


class DingBot(object):
    def __init__(self, webhook):
        self.webhook = webhook

    def send_markdown(self, title, text, is_at_all=False, at_mobiles=[], at_dingtalk_ids=[], is_auto_at=True):
        """
        markdown类型
        :param title: 首屏会话透出的展示内容
        :param text: markdown格式的消息内容
        :param is_at_all: @所有人时：true，否则为：false（可选）
        :param at_mobiles: 被@人的手机号（默认自动添加在text内容末尾，可取消自动化添加改为自定义设置，可选）
        :param at_dingtalk_ids: 被@人的dingtalkId（可选）
        :param is_auto_at: 是否自动在text内容末尾添加@手机号，默认自动添加，可设置为False取消（可选）
        :return: 返回消息发送结果
        """
        if all(map(is_not_null_and_blank_str, [title, text])):
            # 给Mardown文本消息中的跳转链接添加上跳转方式
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": text
                },
                "at": {}
            }
            if is_at_all:
                data["at"]["isAtAll"] = is_at_all

            if at_mobiles:
                at_mobiles = list(map(str, at_mobiles))
                data["at"]["atMobiles"] = at_mobiles
                if is_auto_at:
                    mobiles_text = '\n@' + '@'.join(at_mobiles)
                    data["markdown"]["text"] = text + mobiles_text

            if at_dingtalk_ids:
                at_dingtalk_ids = list(map(str, at_dingtalk_ids))
                data["at"]["atDingtalkIds"] = at_dingtalk_ids
            return self.post(data)
        else:
            raise ValueError("markdown类型中消息标题或内容不能为空！")

    def post(self, body):
        response = requests.post(self.webhook, json=body)
        print(f'钉钉通知！resp: {response.text}, request_body: {body}')
