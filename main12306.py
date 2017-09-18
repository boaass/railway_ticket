# -*-coding:utf-8 -*-

from login12306 import RailwayLoginTool
from search12306 import SearchTicket
from buy12306 import BuyTicket
import time
import ConfigParser


def main():
    cf = ConfigParser.ConfigParser()
    cf.read('user.cfg')

    username = cf.get('login', 'username')
    password = cf.get('login', 'password')

    isLogin = False
    while not isLogin:
        while len(username) == 0 or len(password) == 0:
            username = raw_input('Please input username: ')
            password = raw_input('Please input password: ')
            continue

        login = RailwayLoginTool(username=username, password=password)
        isLogin = login.isLogin()

        if isLogin:
            continue
        isLogin = login.login()
        if isLogin is False:
            cf.set('login', 'username', '')
            cf.set('login', 'password', '')
            cf.write(open("user.cfg", "w"))
            username = password = ''
        else:
            # cf.add_section('login')
            cf.set('login', 'username', username)
            cf.set('login', 'password', password)
            cf.write(open("user.cfg", "w"))

    print '------------------'
    all_buyer_infos = login.get_buyer_list()
    index = 0
    for buyer in all_buyer_infos:
        print '|' + '   ' + str(index) + '. ' + buyer['passenger_name']
        index += 1
    print '------------------'

    buyers = raw_input('请输入购买人序号(逗号分隔): ').split(',')
    buyer_infos = []
    for buyer_index in buyers:
        if not buyer_index == '':
            buyer_infos.append(all_buyer_infos[int(buyer_index)])
    print buyer_infos

    search = SearchTicket(start=u'北京', to=u'于家堡', trains=[u'C2593'], dates=[u'2017-09-24'])
    flag = 1
    ticket_infos = []
    while flag:
        ticket_infos = search.request_ticket_info()
        if ticket_infos and len(ticket_infos) != 0:
            flag = 0
        else:
            print '对应车次无票'
        time.sleep(2)

    print ticket_infos
    # for ticket_info in ticket_infos:
    ticket_info = ticket_infos[0]
    buy = BuyTicket(train_date=ticket_info['from_date_search'],
                    from_station=ticket_info['from_station'],
                    from_station_ab=ticket_info['from_station_ab'],
                    to_station=ticket_info['to_station'],
                    to_station_ab=ticket_info['to_station_ab'],
                    train_no=ticket_info['train_no'],
                    train_number=ticket_info['train_number'],
                    train_location=ticket_info['train_location'],
                    left_ticket=ticket_info['left_ticket'],
                    secret_str=ticket_info['secret_str'],
                    seat_type=ticket_info['seat_type'],
                    buyer_infos=buyer_infos)

if __name__ == '__main__':
    main()












