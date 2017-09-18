# coding: utf-8

import re, time
import threading
import requests, json, cookielib
from random import choice
from IPProxyTool import IPProxyTool
from apscheduler.schedulers.blocking import BlockingScheduler
from Logging import Logging
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import logging

logging.basicConfig()
# 禁用安全请求警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

DOMAIN = u'https://kyfw.12306.cn'
save_query_log_url = u'https://kyfw.12306.cn/otn/leftTicket/log'
INITURL = u'https://kyfw.12306.cn/otn/leftTicket/init'
check_user_url = u"https://kyfw.12306.cn/otn/login/checkUser"


def stringByAppendingPathComponent(suffix_str, end_str):
    """
    拼接网址或者路径
    :param suffix_str:  首部字符串
    :param end_str:     尾部字符串
    :return:            拼接后的字符串
    """
    suffix_str = suffix_str[:-1] if suffix_str.endswith('/') else suffix_str
    end_str = '/' + end_str if not end_str.startswith('/') else end_str

    return suffix_str + end_str


class SearchTicket(object):
    # 无座和其他等不支持自选席位的类型，需要二次验证，暂不支持
    seat_type = [u'商务特等座', u'一等座', u'二等座', u'硬座', u'硬卧', u'无座', u'软座', u'软卧', u'其他', u'高级软卧']

    def __init__(self, start, to, trains=None, dates=None, seat_types=None, delay=5):

        cookies = cookielib.LWPCookieJar('cookies')
        self.session = requests.session()
        self.session.cookies = cookies
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36',
            'Content-Type': 'application/json;charset=UTF-8',
            'cache-control': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, br'}
        self.session.headers = headers
        try:
            self.session.cookies.load(ignore_discard=True)
        except Exception as e:
            Logging.debug(e.message)
            Logging.warning("cookies 加载失败 !!! 如需订票，请重新运行 'login12306.py'验证登录 !!!")

        self.session.cookies = requests.utils.add_dict_to_cookiejar(self.session.cookies, {"current_captcha_type": "Z",
                                                                                           "fp_ver": "4.5.1",
                                                                                           "RAIL_EXPIRATION": str(int(
                                                                                               round(
                                                                                                   time.time() * 1000))
                                                                                           ),
                                                                                           "RAIL_DEVICEID": "JCTFFU_Ut9rAYiNh49CcBhxCWjxxzfRWpEH9MVv78I-EnTFvtJxZopvJjdKInEm2k0gtSfg06x_xnH2FiRak7_uzab62y0QgnW-GmiRG8GCwa3cxSUeuJeqxG9s_mCn-aQ92yA3h8KElnUty4HAOmm6IYxeiXtm7"
                                                                                           })

        self.dates = dates

        # 获取站名及其对应缩写
        self.country_ls_map, self.country_sl_map, CLeftTicketUrl = self.catch_station_map()
        if self.country_ls_map is None:
            Logging.error('country_ls_map is None')
            return

        if self.country_sl_map is None:
            Logging.error('country_sl_map is None')
            return

        if CLeftTicketUrl is None:
            Logging.error('CLeftTicketUrl is None')
            return

        self.start_place_ab = self.country_ls_map.get(start)
        self.to_place_ab = self.country_ls_map.get(to)
        if len(self.start_place_ab) == 0:
            Logging.error("param 'start' is invalid")
            return

        if len(self.to_place_ab) == 0:
            Logging.error("param 'to' is invalid")
            return

        self.target_trains = trains
        self.start_place = start
        self.to_place = to
        self.seat_types = seat_types
        self.delay = delay

        self.request_ticket_urls, self.save_query_urls = self.config_task_urls(stringByAppendingPathComponent(DOMAIN, 'otn/' + CLeftTicketUrl))
        if len(self.request_ticket_urls) == 0:
            Logging.error('request_ticket_urls is None')
            return
        if len(self.save_query_urls) == 0:
            Logging.error('save_query_urls is None')
            return

        # 检查用户登录状态
        self.check_user()

        # 保存查询log(不确定是否有用)
        # self.save_query_log()

    def catch_station_map(self):
        Logging.debug('<---------- 获取站名信息 ---------->')
        try:
            response = self.session.get(INITURL, verify=False)
            CLeftTicketUrl = re.search(r"var\sCLeftTicketUrl\s=\s'(.*?)';", response.text).group(1)

            tag = re.search(r'<script type="text/javascript" src="(.*?station_name.*?)".*</script>',
                            response.text).group(1)
            map_url = stringByAppendingPathComponent(DOMAIN, tag)
            js_rep = self.session.get(map_url, verify=False)
            js_data = re.search(r"'(.*)'", js_rep.text).group(1).split('|')

            key = u''
            country_ls_map = {}
            country_sl_map = {}
            for index in range(len(js_data)):
                if index % 5 == 1:
                    key = js_data[index]
                elif index % 5 == 2:
                    country_ls_map[key] = js_data[index]
                    country_sl_map[js_data[index]] = key
            return country_ls_map, country_sl_map, CLeftTicketUrl
        except Exception as e:
            Logging.warning(e)
            return None, None, None

    def config_task_urls(self, CLeftTicketUrl):
        Logging.debug('<---------- 配置请求url ---------->')

        request_ticket_urls = []
        save_query_urls = []
        for date in self.dates:
            request_ticket_urls.append(
                '%s?leftTicketDTO.train_date=%s&leftTicketDTO.from_station=%s&leftTicketDTO.to_station=%s'
                '&purpose_codes=%s' % (
                    CLeftTicketUrl, date, self.start_place_ab, self.to_place_ab, 'ADULT'))
            save_query_urls.append(
                '%s?leftTicketDTO.train_date=%s&leftTicketDTO.from_station=%s&leftTicketDTO.to_station=%s'
                '&purpose_codes=%s' % (
                    save_query_log_url, date, self.start_place_ab, self.to_place_ab,
                    'ADULT'))
        return request_ticket_urls, save_query_urls

    def start(self, min_ip_count=5):
        Logging.debug('<---------- 设置代理定时任务 ---------->')
        proxy_thread = threading.Thread(target=self.proxy_schedule)
        proxy_thread.setDaemon(True)
        Logging.debug('<---------- 获取代理 ---------->')
        self.request_proxy(min_ip_count=min_ip_count)

        # 设置获取票信息定时任务
        ticket_thread = threading.Thread(target=self.ticket_schedule)
        ticket_thread.setDaemon(True)

        ticket_thread.start()
        proxy_thread.start()

    def check_user(self):
        Logging.debug('<---------- 检查用户登录状态 ---------->')
        res = self.session.post(check_user_url, verify=False)
        Logging.debug(res.text)

    def save_query_log(self):
        Logging.debug('<---------- 保存查询log ---------->')
        for url in self.save_query_urls:
            Logging.debug(url)
            res = self.session.get(url, verify=False)
            # Logging.debug(res.text)

    def request_ticket_info(self):
        Logging.debug('<---------- 请求车票信息 ---------->')
        train_infos = []

        for url in self.request_ticket_urls:
            proxies = []
            for ip in IPProxyTool().getIPs():
                proxies.append(dict(http='http://' + ip, https='http://' + ip))

            print url
            if len(proxies) != 0:
                response = self.session.get(url, verify=False, proxies=choice(proxies))
            else:
                response = self.session.get(url, verify=False)
            try:
                if response.status_code == 200:
                    # Logging.debug(requests.utils.dict_from_cookiejar(self.session.cookies))
                    self.session.cookies.save(ignore_discard=True)
                    info_json = response.json()
                    result = info_json['data']['result']
                    train_infos.append(result)
                else:
                    Logging.warning(response.text.encode('u8'))
                    continue
            except Exception as e:
                Logging.debug(response.text)
                Logging.warning(e.message)
                continue
        return self.parse_result(train_infos)

    def request_proxy(self, min_ip_count=5):
        IPProxyTool().destIP = INITURL
        IPProxyTool().refresh(min_ip_count=min_ip_count)

    def parse_result(self, train_infos):
        Logging.debug('<---------- 解析车票信息 ---------->')
        valid_train_infos = []
        for train_info in train_infos:
            results = train_info
            for result in results:
                try:
                    search_result = re.search(ur'\|?(.*?)(\|预订\|.*)', result)
                    train_data_list = search_result.group(2).split('|')
                    if len(search_result.group(1)) != 0:
                        train_data_list.insert(0, search_result.group(1))
                    else:
                        train_data_list.insert(0, "")

                    train_data_list.reverse()
                    if self.target_trains is None or len(self.target_trains) == 0:
                        # 返回全部有效的车次信息
                        valid_train_info = self.structure_result(train_data_list)
                        valid_train_infos.append(valid_train_info) if valid_train_info is not None else None
                    else:
                        # 返回指定查询的有效的车次信息
                        for target_train in self.target_trains:
                            for train_data in train_data_list:
                                if target_train in train_data:
                                    valid_train_info = self.structure_result(train_data_list)
                                    valid_train_infos.append(valid_train_info) if valid_train_info is not None else None
                except Exception as e:
                    Logging.warning(e.message)

        # print valid_train_infos
        # print json.dumps(valid_train_infos, encoding='UTF-8', ensure_ascii=False)
        return valid_train_infos

    def structure_result(self, train_data_list):
        if train_data_list[24] == u'N':
            return None

        valid_train_info = {}
        valid_train_info.update({self.seat_type[0]: train_data_list[3]}) \
            if len(train_data_list[3]) > 0 and train_data_list[3] != u'无' else None
        valid_train_info.update({self.seat_type[1]: train_data_list[4]}) \
            if len(train_data_list[4]) > 0 and train_data_list[4] != u'无' else None
        valid_train_info.update({self.seat_type[2]: train_data_list[5]}) \
            if len(train_data_list[5]) > 0 and train_data_list[5] != u'无' else None
        valid_train_info.update({self.seat_type[3]: train_data_list[6]}) \
            if len(train_data_list[6]) > 0 and train_data_list[6] != u'无' else None
        valid_train_info.update({self.seat_type[4]: train_data_list[7]}) \
            if len(train_data_list[7]) > 0 and train_data_list[7] != u'无' else None
        # valid_train_info.update({self.seat_type[5]: train_data_list[9]}) \
        #     if len(train_data_list[9]) > 0 and train_data_list[9] != u'无' else None
        valid_train_info.update({self.seat_type[6]: train_data_list[11]}) \
            if len(train_data_list[11]) > 0 and train_data_list[11] != u'无' else None
        valid_train_info.update({self.seat_type[7]: train_data_list[12]}) \
            if len(train_data_list[12]) > 0 and train_data_list[12] != u'无' else None
        # valid_train_info.update({self.seat_type[8]: train_data_list[12]}) \
        #     if len(train_data_list[13]) > 0 and train_data_list[13] != u'无' else None
        valid_train_info.update({self.seat_type[9]: train_data_list[14]}) \
            if len(train_data_list[14]) > 0 and train_data_list[14] != u'无' else None

        for seat_type in valid_train_info.iterkeys():
            if len(seat_type) > 0:
                if self.seat_types is None or len(self.seat_types) == 0 or seat_type in self.seat_types:
                    # 翻转list
                    train_data_list.reverse()
                    print train_data_list
                    valid_train_info['secret_str'] = train_data_list[0]
                    valid_train_info['train_no'] = train_data_list[3]
                    valid_train_info['train_number'] = train_data_list[4]
                    valid_train_info['from_station'] = self.country_sl_map[train_data_list[7]]
                    valid_train_info['to_station'] = self.country_sl_map[train_data_list[8]]
                    valid_train_info['from_date'] = train_data_list[9]
                    valid_train_info['to_date'] = train_data_list[10]
                    valid_train_info['left_ticket'] = train_data_list[13]
                    valid_train_info['from_station_ab'] = self.country_ls_map.get(self.start_place)
                    valid_train_info['to_station_ab'] = self.country_ls_map.get(self.to_place)
                    valid_train_info['from_date_search'] = train_data_list[14][0:4] + '-' + train_data_list[14][
                                                                                            4:6] + '-' + \
                                                           train_data_list[14][6:]
                    valid_train_info['train_location'] = train_data_list[16]
                    valid_train_info['seat_type'] = seat_type
                    return valid_train_info

        return None

    def ticket_schedule(self):
        Logging.debug('<---------- 开始定时任务:获取车票信息 --------->')
        scheduler = BlockingScheduler()
        scheduler.add_job(self.request_ticket_info, 'interval', seconds=5, max_instances=5)
        scheduler.start()

    def proxy_schedule(self):
        Logging.debug('<---------- 开始定时任务:获取代理 --------->')
        scheduler = BlockingScheduler()
        scheduler.add_job(self.request_proxy, 'interval', seconds=300, max_instances=5)
        scheduler.start()


# searcher = SearchTicket(start=u'北京南', to=u'于家堡', dates=[u'2017-09-23'], trains=[u'C2593'], seat_types=[u'二等座'], delay=1000)
# searcher.start()
# print json.dumps(searcher.request_ticket_info(), encoding='u8', ensure_ascii=False)

# while 1:
#     num = 1
