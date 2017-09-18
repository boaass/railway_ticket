# -*- coding:utf8 -*-

import requests
import os, platform, re, json, cookielib
from Logging import Logging
from Singleton import Singleton

# 禁用安全请求警告
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class RailwayLoginTool(Singleton):
    domain = "https://kyfw.12306.cn"
    init_url = "https://kyfw.12306.cn/otn/login/init"
    check_user_url = "https://kyfw.12306.cn/otn/login/checkUser"
    user_login_url = "https://kyfw.12306.cn/otn/login/userLogin"

    def __init__(self, username=None, password=None):

        self.cookies = cookielib.LWPCookieJar('cookies')
        self.session = requests.Session()
        self.session.cookies = self.cookies

        Logging.debug('<---------- 正在初始化 ---------->')

        self.username = username
        self.password = password
        Logging.debug('<---------- 登录用户名:%s ---------->' % self.username.encode('u8'))
        Logging.debug('<---------- 登录密码:%s ---------->' % self.password.encode('u8'))

        res = self.session.get(self.init_url, verify=False)
        if res.status_code == 200:
            try:
                self.passport_appId = re.search(r"var\spassport_appId\s=\s'(.*)'", res.text).group(1)
                Logging.debug('获取passport_appId:%s' % self.passport_appId.encode(res.encoding))
                self.passport_captcha_url = re.search(r"var\spassport_captcha\s=\s'(http.*)'", res.text).group(1)
                Logging.debug('获取验证码url:%s' % self.passport_captcha_url.encode(res.encoding))
                self.passport_captcha_check_url = re.search(r"var\spassport_captcha_check\s=\s'(http.*)'",
                                                            res.text).group(1)
                Logging.debug('获取验证码验证url:%s' % self.passport_captcha_check_url.encode(res.encoding))
                self.passport_authuam_url = re.search(r"var\spassport_authuam\s=\s'(http.*)'", res.text).group(1)
                Logging.debug('获取时效验证url:%s' % self.passport_authuam_url.encode(res.encoding))
                self.passport_login = re.search(r"var\spassport_login\s=\s'(http.*)'", res.text).group(1)
                Logging.debug('获取登录url:%s' % self.passport_login.encode(res.encoding))
                self.uamauthclient = "https://kyfw.12306.cn/otn/uamauthclient"
            except Exception as e:
                Logging.error('%s' % e)

    def login(self):
        Logging.debug('<---------- 正在登录 ---------->')

        captcha_name = self.get_captcha()
        if captcha_name == None or len(captcha_name) == 0:
            return False

        # self.get_uam()

        answer = self.parse_captcha(captcha_name)
        captcha_check_param = dict(answer=answer, login_site='E', rand='sjrand')
        # Logging.debug('验证码请求验证参数:%s' % captcha_check_param)

        res = self.session.get(self.passport_captcha_check_url, params=captcha_check_param, verify=False)
        if res.status_code == 200:
            result = json.loads(res.text)
            if result['result_code'] == '4':
                Logging.debug('<---------- 验证成功 ---------->')
            else:
                Logging.debug('<---------- %s ---------->' % result['result_message'])
                return False
        else:
            Logging.error('<---------- 验证失败 ---------->')
            return False

        login_params = dict(username=self.username, password=self.password, appid=self.passport_appId)
        res = self.session.post(self.passport_login, params=login_params)
        try:
            if json.loads(res.text)['result_code'] == 0:
                Logging.debug('<---------- 登录成功 ---------->')
                Logging.info(res.text)
                # Logging.info(requests.utils.dict_from_cookiejar(self.session.cookies))

                user_login_res = self.session.post(self.user_login_url, verify=False, allow_redirects=False)
                Logging.debug(user_login_res.headers)
                try:
                    Logging.debug('<---------- 获取登录重定向url ---------->')
                    redirect_login_url = user_login_res.headers['Location']
                    Logging.debug('redirect_login_url: %s' % redirect_login_url)
                    Logging.debug(user_login_res.headers)
                    Logging.debug('<---------- 重定向获取 JSESSIONID ---------->')
                    redirect_res = self.session.get(redirect_login_url, verify=False)
                    Logging.debug(redirect_res.headers)
                    # Logging.info(requests.utils.dict_from_cookiejar(self.session.cookies))

                    Logging.debug('<---------- 获取token ---------->')
                    token = self.get_uam()
                    if token is None or len(token) == 0:
                        return False
                    else:
                        Logging.debug('<---------- 将token保存进cookies ---------->')
                        res = self.session.post(self.uamauthclient, params={'tk':token}, verify=False)
                        res_json = json.loads(res.text)
                        Logging.debug('<---------- %s ---------->' % res_json['result_message'].encode('u8'))
                        if res_json['result_code'] != 0:
                            return False
                        self.session.cookies.save(ignore_discard=True)
                        return True
                except Exception as e:
                    Logging.warning(e)
                    return False
            else:
                Logging.debug('<---------- 登录失败 ---------->')
                Logging.debug(res.text)
                return False
        except Exception as e:
            Logging.warning(e)
            return False

    def isLogin(self):
        Logging.debug('<---------- 判断登录状态 ---------->')
        try:
            self.session.cookies.load(ignore_discard=True)
            tk = requests.utils.dict_from_cookiejar(self.session.cookies)['tk']
            res = self.session.post(self.check_user_url, params={'_json_att': ''}, verify=False)
            res_json = json.loads(res.text)
            return res_json['data']['flag']
        except Exception as e:
            Logging.debug(e.message)
            Logging.warning("cookies 加载失败 !!! 请重新运行 'login12306.py'验证登录 !!!")
            return False

    def get_captcha(self):
        captcha_param = dict(login_site='E', module='login', rand='sjrand')
        Logging.debug('验证码请求参数:%s' % captcha_param)

        Logging.debug('<---------- 获取验证码 ---------->')
        res = self.session.get(self.passport_captcha_url, params=captcha_param, verify=False)
        if res.status_code == 200:
            captcha_name = 'captcha-image.png'
            with open(captcha_name, 'wb') as f:
                for data in res.iter_content(chunk_size=1024):
                    if data:
                        f.write(data)
                        f.flush()
                f.close()

            Logging.debug('<---------- 获取验证码成功 ---------->')
            return captcha_name
        else:
            Logging.error('<---------- 获取验证码失败 ---------->')
            return None

    def get_uam(self):
        Logging.debug('<---------- 获取时效信息 ---------->')
        res = self.session.post(self.passport_authuam_url, params=dict(appid=self.passport_appId), verify=False)
        try:
            res_json = json.loads(res.text)
            Logging.debug('<---------- 获取时效信息: %s ---------->' % res_json["result_message"].encode('u8'))
            if res_json['result_code'] == 0:
                if res_json["apptk"]:
                    return res_json["apptk"]
                elif len(res_json["newapptk"]) is not 0:
                    return res_json["newapptk"]
            else:
                return None
        except Exception as e:
            Logging.debug(res.text.decode('u8'))
            Logging.warning(e.message)

    def parse_captcha(self, image_name):
        Logging.debug('<---------- 解析验证码 ---------->')

        if platform.system() == "Linux":
            Logging.info("Command: xdg-open %s &" % image_name)
            os.system("xdg-open %s &" % image_name)
        elif platform.system() == "Darwin":
            Logging.info("Command: open %s &" % image_name)
            os.system("open %s &" % image_name)
        elif platform.system() in ("SunOS", "FreeBSD", "Unix", "OpenBSD", "NetBSD"):
            os.system("open %s &" % image_name)
        elif platform.system() == "Windows":
            os.system("%s" % image_name)
        else:
            Logging.info("无法获取当前操作系统，请自行打开验证码 %s 文件，并输入验证码。" % os.path.join(os.getcwd(), image_name))

        pic_index_str = raw_input("请输入验证答案(1-8,以','分割)：")
        pic_indexs = pic_index_str.split(',')
        offsetX = 0
        offsetY = 0
        answer = ''
        for pic_index in pic_indexs:
            if pic_index == '1':
                offsetX = '45'
                offsetY = '47'
            elif pic_index == '2':
                offsetX = '110'
                offsetY = '47'
            elif pic_index == '3':
                offsetX = '187'
                offsetY = '44'
            elif pic_index == '4':
                offsetX = '253'
                offsetY = '44'
            elif pic_index == '5':
                offsetX = '46'
                offsetY = '114'
            elif pic_index == '6':
                offsetX = '110'
                offsetY = '114'
            elif pic_index == '7':
                offsetX = '187'
                offsetY = '114'
            elif pic_index == '8':
                offsetX = '253'
                offsetY = '114'
            else:
                Logging.warning('输入的答案无效')
            answer = answer + offsetX + ',' + offsetY + ','
        return answer[:-1]

    def get_buyer_list(self):
        try:
            confirmPassengerInitDc = u'https://kyfw.12306.cn/otn/confirmPassenger/initDc'
            confirmPassengerUrl = u'https://kyfw.12306.cn/otn/confirmPassenger/getPassengerDTOs'
            params = {"_json_att": ""}
            res = self.session.post(confirmPassengerInitDc, params=params, verify=False)
            repeat_token = re.search(r"var\sglobalRepeatSubmitToken\s=\s'(.*?)'", res.text).group(1)
            params = {"_json_att": "", "REPEAT_SUBMIT_TOKEN": repeat_token}
            res = self.session.post(confirmPassengerUrl, params=params, verify=False)
            return json.loads(res.text)['data']['normal_passengers']
        except Exception as e:
            Logging.error(e)
            return None