from get_pokemons import get_location, get_pokemon_within_radius
from IPython import embed
from datetime import datetime, timedelta
import requests
import time
import os

# Set up Telegram bot
pokesg_username = os.environ["TELE_POKESG_USER"]
pokesg_api = os.environ["TELE_POKESG_API"]
endpoint = "https://api.telegram.org/bot{}/".format(pokesg_api)

send_msg = endpoint + "sendMessage"
send_loc = endpoint + "sendLocation"
ep_get_updates = endpoint + "getUpdates"

greetings = '''
Hi, you must be new! I'll need 2 things for you to get started.

(1) Your current location

/setloc <address of current location>
    - Please enter your address or pluscode from google maps.
    - Eg. /setloc 681 race course rd, singapore

(2) Radius in KM

/setradius <number or decimal>
    - Please set your radius in km. Maximum of 5km.
    - Eg. /setradius 1

----------------------------------

Once you have set up these 2, you may use this bot to:
/list
    - List all pokemons within radius of your location

/monitor
    - Monitor your location and radius and notify you of new spawns for the next 1 hour


Other functions:
/settings
    - Check your current location, radius and monitoring settings

/stop
    - Stop the monitoring

/help  or  /start
    - Get back to this screen
'''


def telegram_do(method, params=None, chat_id=None):
    if chat_id:
        params += [('chat_id', chat_id)]
    return requests.get(method, params=params).json()


def get_last_update_id(updates):
    update_ids = []
    for update in updates:
        update_ids.append(int(update["update_id"]))
    return max(update_ids)


def get_all_chats(updates):
    chats = {}
    for update in updates:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"]["text"]
        chats[chat_id] = chats.get(chat_id, [])
        chats[chat_id] += [text]
    return chats
    # telegram_do(send_msg, params=[('text', text)], chat_id=chat)


def get_updates(offset=None, timeout=None):
    params = []
    if offset:
        params += [('offset', str(offset))]
    if timeout:
        params += [('timeout', str(timeout))]
    if params == []:
        params = None
    return telegram_do(ep_get_updates, params=params)['result']


def chat_action_list(chat_id, user, since=None):
    geocode_latlon = user.get("loc", "")
    radius = user.get("radius", "")
    if geocode_latlon == "" and radius == "":
        msg = '''
Unable to list nearby pokemons. You have not set your location and radius.

Please set the address of your current location:
/setloc <address>
Eg. /setloc 681 race course rd, singapore
-- You may copy and paste pluscode from google maps if current location is unknown.

Please set your radius limit in km:
/setradius <number or decimal>
Eg. /setradius 1
-- Please set your radius in km. Maximum of 5km.
        '''
        telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)

    elif geocode_latlon == "":
        msg = '''
Unable to list nearby pokemons. You have not set your location.

Please set the address of your current location:
/setloc <address>
Eg. /setloc 681 race course rd, singapore
-- You may copy and paste pluscode from google maps if current location is unknown.
        '''
        telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)

    elif radius == "":
        msg = '''
Unable to list nearby pokemons. You have not set your radius.

Please set your radius limit in km:
/setradius <number or decimal>
Eg. /setradius 1
-- Please set your radius in km. Maximum of 5km.
        '''
        telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)

    else:
        counter = 0
        sorted_pokemon_within_radius, since = get_pokemon_within_radius(geocode_latlon, radius, since=since)
        if sorted_pokemon_within_radius:
            for pk in sorted_pokemon_within_radius:
                counter += 1
                # print counter, pk["name"].upper()
                message = "{0:<2} {1}\n".format(counter, pk["name"].upper())
                message += "Distance    : {0:<3.2f} km\n".format(pk["km_from_location"])
                message += "Despawn in : {}\n\n".format(pk["time_left_secs"])
                # Send pokemon summary
                msg_params = [('text', message)]
                summary_msg = telegram_do(send_msg, params=msg_params, chat_id=chat_id)
                # Send location of selected pokemon
                latitude = pk['lat']
                longitude = pk['lng']
                loc_params = [('latitude', latitude), ('longitude', longitude)]
                loc = telegram_do(send_loc, params=loc_params, chat_id=chat_id)
        return since


def chat_action_end_monitor(user):
    user["monitor"] = None
    user["monitor_pretty"] = None
    user["since"] = None
    return user


def chat_action(chat, chat_id, user):
    if "/start" in chat or "/help" in chat:
        telegram_do(send_msg, params=[('text', greetings)], chat_id=chat_id)
    elif "/setloc " in chat:
        geocode_latlon, formatted_address = get_location(chat[chat.find("/setloc ")+8:])
        user["loc"] = geocode_latlon
        user["address"] = formatted_address
        msg = "Location set to: {}".format(user["address"])
        telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)
        return user
    elif "/setradius " in chat:
        radius = float(chat[chat.find("/setradius ") + 11:])
        if radius > 5.0:
            msg = "Radius set is greater than 5 km. Please /setradius again."
            telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)
        else:
            user["radius"] = radius
            msg = "Radius set to   : {0:<3.2f} km".format(radius)
            telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)
            return user

    elif "/monitor" in chat:
        since = chat_action_list(chat_id, user)
        if since:
            monitor_till = datetime.now() + timedelta(hours=1)
            monitor_till_ts = int(time.mktime(monitor_till.timetuple()))
            user["monitor"] = monitor_till_ts
            user["monitor_pretty"] = monitor_till.strftime("%Y-%m-%d %-I:%M:%S %p")
            user["since"] = since
            # time_left = datetime.fromtimestamp(monitor_till_ts) - datetime.now()
            # minutes, seconds = divmod(time_left.seconds, 60)
            # print "{:<2} mins {:<2} sec".format(minutes, seconds)
            return user

    elif "/stop" in chat:
        monitoring = user.get("monitor", None)
        if monitoring:
            if monitoring == "Expired":
                msg = "Monitoring has expired."
                telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)
            else:
                msg = "Monitoring stopped."
                telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)
                return chat_action_end_monitor(user)
        else:
            msg = "No monitoring was set up."
            telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)

    elif "/settings" in chat:
        address = user.get("address", None)
        radius = user.get("radius", None)
        monitor_pretty = user.get("monitor_pretty", None)

        if address:
            msg = "Location : {}\n".format(address)
        else:
            msg = "Location : {}\n".format("Not set")

        if radius:
            msg += "Radius    : {} km\n".format(radius)
        else:
            msg += "Radius    : {}\n".format("Not set")

        if monitor_pretty:
            msg += "Monitoring : {}\n".format(monitor_pretty)
        else:
            msg += "Monitoring : {}\n".format("Not set")

        telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)

    elif "/list" in chat:
        chat_action_list(chat_id, user)


def main():
    last_update_id = None
    # users keep prior chats in memory
    users = {}
    # users = {
    #     323679630: {
    #         'loc': (1.305192, 103.7909068),
    #         'radius': 2.0,
    #         'address': u'1 North Buona Vista Drive, Singapore 138675'
    #     },
    #     283535375: {
    #         'loc': (1.3137481, 103.8552258),
    #         # 'monitor': 1492325116,
    #         # 'since': 1492322711,
    #         # 'radius': 1.0,
    #         'address': u'681 Race Course Rd, Singapore',
    #         # 'monitor_pretty': '2017-04-16 2:45:16 PM'
    #     }
    # }
    # Main code
    while True:
        print("getting updates")

        # Monitoring mechanism
        for chat_id in users:
            user = users[chat_id]
            monitor = user.get("monitor", None)
            if monitor:
                if datetime.fromtimestamp(monitor) < datetime.now():
                    users[chat_id] = chat_action_end_monitor(user)
                else:
                    users[chat_id]["since"] = chat_action_list(
                        chat_id, user, since=user["since"])

        # Receiving telegram commands
        updates = get_updates(offset=last_update_id, timeout='100')
        if len(updates) > 0:
            last_update_id = get_last_update_id(updates) + 1

            # Gets only the last updated
            chats = get_all_chats(updates)

            for chat_id in chats:
                if chat_id not in users.keys():
                    telegram_do(send_msg, params=[('text', greetings)], chat_id=chat_id)
                    users[chat_id] = {}
                else:
                    user = users[chat_id]
                    # print users
                    for chat in chats[chat_id]:
                        new_user = chat_action(chat, chat_id, user)
                        if new_user:
                            print "if user"
                            users[chat_id] = new_user
            print users
            time.sleep(0.5)

if __name__ == '__main__':
    main()
