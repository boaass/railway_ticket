# -*- coding:utf-8 -*-

import requests, re, urllib, lxml
import cookielib, json, time
from Logging import Logging
from random import choice
from IPProxyTool import IPProxyTool
from bs4 import BeautifulSoup

# 禁用安全请求警告
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

DOMAIN = u'https://kyfw.12306.cn'
submitOrderRequestUrl = DOMAIN + u'/otn/leftTicket/submitOrderRequest'
confirmPassengerUrl = DOMAIN + u'/otn/confirmPassenger/getPassengerDTOs'
# 单程
confirmPassengerInitDc = DOMAIN + u'/otn/confirmPassenger/initDc'
queueCountUrl = DOMAIN + u'/otn/confirmPassenger/getQueueCount'
confirmSingleForQueueUrl = DOMAIN + u'/otn/confirmPassenger/confirmSingleForQueue'


def url_encode(str):
    try:
        for s in str:
            if u'\u4e00' <= s <= u'\u9fff':
                # 中文
                str = str.replace(s, hex(ord(s))).upper()
            elif s.isdigit():
                # 数字
                continue
            elif s.isalpha():
                # 字母
                continue
            else:
                str = str.replace(s, urllib.quote(s)).upper()

        str = str.replace('0X', '%u')
        return str
    except Exception as e:
        print e
        return None

def url_decode(str):
    try:
        for i in re.compile('%u[0-9A-Z]{4}').findall(str):
            str = str.replace(i, unichr(int(i[2:], 16)))
        str = str.replace('%2C', ',')
        return str
    except Exception as e:
        print e.message

class BuyTicket(object):
    def __init__(self,
                 train_date=None,
                 from_station=None,
                 from_station_ab=None,
                 to_station=None,
                 to_station_ab=None,
                 train_no=None,
                 train_number=None,
                 train_location=None,
                 secret_str=None,
                 left_ticket=None,
                 seat_type=None,
                 buyer_infos=None):

        Logging.debug('<---------- 初始化订票 ---------->')
        cookies = cookielib.LWPCookieJar('cookies')
        self.session = requests.session()
        self.session.cookies = cookies
        headers = dict(self.session.headers, **{"If-Modified-Since": "0",
                                                "Cache-Control": "no-cache",
                                                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36",
                                                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                                                "Accept-Encoding": "gzip, deflate, br",
                                                "Accept-Language": "zh-CN,zh;q=0.8,en;q=0.6",
                                                "Content-Type": "application/x-www-form-urlencoded"})
        self.session.headers = headers
        try:
            self.session.cookies.load(ignore_discard=True)
        except Exception as e:
            Logging.debug(e.message)
            Logging.warning("cookies 加载失败 !!! 请重新运行 'login12306.py'验证登录 !!!")

        self.train_data = train_date
        self.from_station = from_station
        self.from_station_ab = from_station_ab
        self.to_station = to_station
        self.to_station_ab = to_station_ab
        self.train_no = train_no
        self.train_number = train_number
        self.train_location = train_location
        self.left_ticket = left_ticket
        self.secret_str = secret_str
        self.seat_type = seat_type
        self.buyer_infos = buyer_infos
        self.passengerTicketStr = ''
        self.oldPassengerStr = ''

        # 设置cookies
        self.prepare()

        # 提交订单，替换 JSESSIONID 或者 tk
        self.submitOrder()

        # 获取repeat_submit_token
        self.seatDetailType, self.key_check_isChange, self.repeat_token, self.seat_type_map, self.ticket_type_map, self.card_type_map, self.purpose_codes, self.isDw = self.get_repeat_submit_token()
        if self.repeat_token is None or self.key_check_isChange is None:
            return

        # 获取可选购买者信息
        self.get_buyer_list()

        # 检查订单信息
        self.check_order_info()

        # 获取车票详细信息
        self.get_queue_count()

        # 确认订单
        self.confirm_order()

    def prepare(self):
        Logging.debug('<---------- 添加购票信息到token ---------->')
        add_cookies = {"_jc_save_fromStation": url_encode(self.from_station)+urllib.quote(',')+self.from_station_ab,
                       "_jc_save_toStation": url_encode(self.to_station)+urllib.quote(',')+self.to_station_ab,
                       "_jc_save_fromDate": self.train_data,
                       "_jc_save_toDate": time.strftime("%Y-%m-%d", time.localtime()),
                       "_jc_save_wfdc_flag": "dc"}
        self.session.cookies = requests.utils.add_dict_to_cookiejar(self.session.cookies, add_cookies)
        print requests.utils.dict_from_cookiejar(self.session.cookies)
        self.session.cookies.save(ignore_discard=True)

    def submitOrder(self):
        Logging.debug('<---------- 上传订单 ---------->')
        session_dict = requests.utils.dict_from_cookiejar(self.session.cookies)
        params = {"secretStr": urllib.unquote(self.secret_str),
                  "train_date": session_dict["_jc_save_fromDate"],
                  "back_train_date": session_dict["_jc_save_toDate"],
                  "tour_flag": session_dict["_jc_save_wfdc_flag"],
                  "purpose_codes": "ADULT",
                  "query_from_station_name": self.from_station,
                  "query_to_station_name": self.to_station,
                  "undefined": ""}
        # Logging.debug(urllib.unquote(self.secret_str))

        res = self.session.post(submitOrderRequestUrl, params=params, verify=False)
        Logging.debug(res.text)

    def get_repeat_submit_token(self):
        Logging.debug('<---------- 获取REPEATSUBMITTOKEN ---------->')
        params = {"_json_att": ""}

        proxy_ips = []
        for ip in IPProxyTool().getIPs():
            proxy_ips.append(dict(http='http://' + ip, https='http://' + ip))

        Logging.debug(requests.utils.dict_from_cookiejar(self.session.cookies))

        if proxy_ips and len(proxy_ips) != 0:
            res = self.session.post(confirmPassengerInitDc, params=params, proxies=choice(proxy_ips), verify=False)
        else:
            res = self.session.post(confirmPassengerInitDc, params=params, verify=False)
            # Logging.debug(res.text)
        try:
            isDw = re.search(r"var\sisDw='(.*?)';", res.text).group(1)
            purpose_codes = re.search(r"'purpose_codes':'(.*?)'", res.text).group(1)
            init_seatTypes = re.search(r"var\sinit_seatTypes=(.*?);", res.text).group(1)
            seat_type_map = {}
            for seat_type in json.loads(init_seatTypes.replace("\'", "\"")):
                    seat_type_map[seat_type['value']] = seat_type['id']
            # Logging.debug(seat_type_map)

            defaultTicketTypes = re.search(r"var\sdefaultTicketTypes=(.*?);", res.text).group(1)
            ticket_type_map = {}
            for ticket_type in json.loads(defaultTicketTypes.replace("\'", "\"")):
                ticket_type_map[ticket_type['value']] = ticket_type['id']
            # Logging.debug(ticket_type_map)

            init_cardTypes = re.search(r"var\sinit_cardTypes=(.*?);", res.text).group(1)
            card_type_map = {}
            for card_type in json.loads(init_cardTypes.replace("\'", "\"")):
                card_type_map[card_type['value']] = card_type['id']
            # Logging.debug(card_type_map)

            repeat_token = re.search(r"var\sglobalRepeatSubmitToken\s=\s'(.*?)'", res.text).group(1)
            re_form = re.search(r'var\sticketInfoForPassengerForm=(.*?);', res.text).group(1)
            key_check_isChange = json.loads(re_form.replace("\'", "\""))['key_check_isChange']

            soup = BeautifulSoup(res.text, 'lxml')
            seatDetailType = ''
            for r in soup.find_all(attrs={"class": "num"}):
                seatDetailType+=r.text

            Logging.debug('<---------- seatDetailType:%s ---------->' % seatDetailType)
            Logging.debug('<---------- key_check_isChange:%s ---------->' % key_check_isChange)
            Logging.debug('<---------- REPEATSUBMITTOKEN:%s ---------->' % repeat_token)

            return seatDetailType, key_check_isChange, repeat_token, seat_type_map, ticket_type_map, card_type_map, purpose_codes, isDw
        except Exception as e:
            Logging.warning(e.message)
            return None, None, None, None, None, None, None, None

    def get_buyer_list(self):
        try:
            params = {"_json_att": "", "REPEAT_SUBMIT_TOKEN": self.repeat_token}
            res = self.session.post(confirmPassengerUrl, params=params, verify=False)
            return json.loads(res.text)['data']['normal_passengers']
        except Exception as e:
            Logging.error(e)
            return None

    def check_order_info(self):
        Logging.debug('<---------- 检查订单信息 ---------->')
        url = DOMAIN + '/otn/confirmPassenger/checkOrderInfo'

        for buyer_info in self.buyer_infos:
            Logging.debug(json.dumps(buyer_info))
            self.passengerTicketStr += '%s,%s,%s,%s,%s,%s,%s,%s_' % (
                self.seat_type_map[self.seat_type], '0', buyer_info['passenger_type'], buyer_info['passenger_name'], buyer_info['passenger_id_type_code'], buyer_info['passenger_id_no'], buyer_info['mobile_no'], 'N')
            self.oldPassengerStr += '%s,%s,%s,%s_' % (buyer_info['passenger_name'], buyer_info['passenger_id_type_code'], buyer_info['mobile_no'], buyer_info['passenger_type'])

        params = {
            'cancel_flag': '2',
            'bed_level_order_num': '000000000000000000000000000000',
            # 座位类型 + '0' + 车票类型 + 购买人姓名 + 身份证类型 + 身份证号码 + 电话号码 + 是否保存
            'passengerTicketStr': self.passengerTicketStr[:-1],
            # 购买人 + 身份证类型 + 身份证 + 购买人类型(成人)
            'oldPassengerStr': self.oldPassengerStr,
            'tour_flag': 'dc',
            'randcode': '',
            '_json_att': '',
            'REPEAT_SUBMIT_TOKEN': self.repeat_token
        }

        Logging.debug(json.dumps(params))

        res = self.session.post(url, params=params, verify=False)
        self.session.cookies.save(ignore_discard=True)
        Logging.debug(res.text)

    def get_queue_count(self):
        Logging.debug('<---------- 获取剩余车票具体信息 ---------->')
        params = {
            'train_date': time.strftime('%a %b %d %Y %X GMT+0800 (CST)', time.strptime(self.train_data, '%Y-%m-%d')),
            'train_no': self.train_no,
            'stationTrainCode': self.train_number,
            'seatType': self.seat_type_map[self.seat_type],
            'fromStationTelecode': self.from_station_ab,
            'toStationTelecode': self.to_station_ab,
            'leftTicket': self.left_ticket,
            'purpose_codes': self.purpose_codes,
            'train_location': self.train_location,
            'REPEAT_SUBMIT_TOKEN': self.repeat_token,
            '_json_att': ''
        }

        Logging.debug(params)
        res = self.session.post(queueCountUrl, params=params, verify=False)
        Logging.debug(res.text)

    def confirm_order(self):
        Logging.debug('<---------- 确认订单 ---------->')

        params = {
            'passengerTicketStr': self.passengerTicketStr,
            'oldPassengerStr': self.oldPassengerStr,
            'randCode': '',
            'purpose_codes': self.purpose_codes,
            'key_check_isChange': self.key_check_isChange,
            'leftTicketStr': self.left_ticket,
            'train_location': self.train_location,
            'choose_seats': '',
            'seatDetailType': self.seatDetailType,
            'roomType': '00',
            'dwAll': self.isDw
        }
        Logging.debug(json.dumps(params))

        try:
            res = self.session.post(confirmSingleForQueueUrl, params=params, verify=False)
            res_text = json.loads(res.text)
            Logging.debug(res_text)
            if res_text['status'] == 'True' and res_text['httpstatus'] == 200:
                Logging.debug('<---------- 订票成功 ---------->')
                return True
            else:
                Logging.debug('<---------- 订票失败 ---------->')
                return False
        except Exception as e:
            Logging.error(e.message)
            return False

# BuyTicket(train_date='2017-09-10', from_station='VNP', to_station='YKP')
