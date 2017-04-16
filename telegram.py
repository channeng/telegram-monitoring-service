from pokemap import get_location, get_pokemons
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

/stop
    - Stop the monitoring

Navigation functions:
/settings
    - Check your current location, radius and monitoring settings
    - Also shows IV filter, excluded and included pokemons

/help  or  /start
    - Get back to this screen

----------------------------------

For more filters, tap /more

Thanks and enjoy!
'''

more_filters = '''
You may set other filters too, such as:
/filteriv <number>
    - Filter for iv greater than specified %. By default, no IV filter is set.
    - Eg. /filteriv 80

/clearfilter
    - Clears your pre-set IV filter. Restore to default. No IV filter is set.

/exclude <pokemon>
    - Excludes a particular pokemon from being tracked
    - Eg. /exclude dratini

/include
    - Clears your existing exclusion list

/include <pokemon>
    - Includes a particular pokemon for tracking
    - Eg. /include dratini
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


def chat_action_list(chat_id, user, since=None, monitor=False):
    geocode_latlon = user.get("loc", "")
    radius = user.get("radius", "")
    filter_iv = user.get("iv", None)

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
        sorted_pokemon_within_radius, since = get_pokemons(
            geocode_latlon, radius, filter_iv=filter_iv, since=since)
        if sorted_pokemon_within_radius:
            for pk in sorted_pokemon_within_radius:
                counter += 1
                # print counter, pk["name"].upper()
                message = "{0:<2} {1}\n".format(counter, pk["name"].upper())
                message += "Distance    : {0:<3.2f} km\n".format(pk["km_from_location"])
                message += "IV percent  : {0:<3} %\n".format(pk["iv"])
                message += "Despawn in : {}\n\n".format(pk["time_left_secs"])
                # Send pokemon summary
                msg_params = [('text', message)]
                summary_msg = telegram_do(send_msg, params=msg_params, chat_id=chat_id)
                # Send location of selected pokemon
                latitude = pk['lat']
                longitude = pk['lng']
                loc_params = [('latitude', latitude), ('longitude', longitude)]
                loc = telegram_do(send_loc, params=loc_params, chat_id=chat_id)
        else:
            if not monitor:
                message = "Sorry, no pokemons found nearby :/"
                msg_params = [('text', message)]
                summary_msg = telegram_do(send_msg, params=msg_params, chat_id=chat_id)
        return since


def chat_action_end_monitor(user):
    user["monitor"] = None
    user["monitor_pretty"] = None
    user["since"] = None
    return user


def chat_action_set_loc(chat, chat_id, user):
    get_string = chat[chat.find("/setloc ")+8:].lower()
    # Check if 'sg' or 'singapore' found within address
    add_tokens = get_string.split(" ")
    if "sg" not in add_tokens and "singapore" not in add_tokens:
        add_tokens += ["Singapore"]
        get_string = " ".join(add_tokens)

    geocode_latlon, formatted_address = get_location(get_string)
    user["loc"] = geocode_latlon
    user["address"] = formatted_address
    msg = "Location set to: {}".format(user["address"])
    telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)
    return user


def chat_action_set_radius(chat, chat_id, user):
    get_string = chat[chat.find("/setradius ") + 11:].lower().replace("km", "")
    radius = float(get_string)
    if radius > 5.0:
        msg = "Radius set is greater than 5 km. Please /setradius again."
        telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)
    else:
        user["radius"] = radius
        msg = "Radius set to   : {0:<3.2f} km".format(radius)
        telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)
        return user


def chat_action_monitor(chat_id, user):
    since = chat_action_list(chat_id, user)
    if since:
        monitor_till = datetime.now() + timedelta(hours=1)
        monitor_till_ts = int(time.mktime(monitor_till.timetuple()))
        monitor_pretty = monitor_till.strftime("%Y-%m-%d %-I:%M:%S %p")
        user["monitor"] = monitor_till_ts
        user["monitor_pretty"] = monitor_pretty
        user["since"] = since
        # time_left = datetime.fromtimestamp(monitor_till_ts) - datetime.now()
        # minutes, seconds = divmod(time_left.seconds, 60)
        # print "{:<2} mins {:<2} sec".format(minutes, seconds)
        msg = "Monitoring set until : {}\n\nTo undo, tap /stop".format(monitor_pretty)
        telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)
        return user


def chat_action_stop_monitor(chat_id, user):
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


def chat_action_settings(chat_id, user):
    address = user.get("address", None)
    radius = user.get("radius", None)
    filter_iv = user.get("iv", None)
    monitor_pretty = user.get("monitor_pretty", None)

    if address:
        msg = "Location : {}\n".format(address)
    else:
        msg = "Location : {}\n".format("Not set")

    if radius:
        msg += "Radius    : {} km\n".format(radius)
    else:
        msg += "Radius    : {}\n".format("Not set")

    if filter_iv:
        msg += "IV filtered > {} %\n".format(filter_iv)

    if monitor_pretty:
        msg += "Monitoring : {}\n".format(monitor_pretty)
    else:
        msg += "Monitoring : {}\n".format("Not set")

    telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)


def chat_action_filter_iv(chat, chat_id, user):
    get_string = chat[chat.find("/filteriv ") + 10:].lower().replace("%", "")
    iv = int(get_string)
    if iv < 0 or iv > 100:
        msg = "IV filter must be between 0 - 100. Please /filteriv again."
        telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)
    else:
        user["iv"] = iv
        msg = "IV filter set to   : {0:<3} %\n\nTo undo, tap /clearfilter".format(iv)
        telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)
        return user


def chat_action_clear_filter_iv(chat_id, user):
    filter_iv = user.get("iv", None)
    if filter_iv:
        msg = "Cleared IV filter.\nCheck your settings here: /settings\n"
        telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)
        user["iv"] = None
        return user
    else:
        msg = "No IV filter was set up."
        telegram_do(send_msg, params=[('text', msg)], chat_id=chat_id)


def chat_action(chat, chat_id, user):
    if "/start" in chat or "/help" in chat:
        telegram_do(send_msg, params=[('text', greetings)], chat_id=chat_id)

    elif "/more" in chat:
        telegram_do(send_msg, params=[('text', more_filters)], chat_id=chat_id)

    elif "/setloc " in chat:
        return chat_action_set_loc(chat, chat_id, user)

    elif "/setradius " in chat:
        return chat_action_set_radius(chat, chat_id, user)

    elif "/monitor" in chat:
        return chat_action_monitor(chat_id, user)

    elif "/filteriv " in chat:
        return chat_action_filter_iv(chat, chat_id, user)

    elif "/clearfilter" in chat:
        return chat_action_clear_filter_iv(chat, chat_id, user)

    elif "/stop" in chat:
        return chat_action_stop_monitor(chat_id, user)

    elif "/settings" in chat:
        chat_action_settings(chat_id, user)

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
                        chat_id, user, since=user["since"], monitor=True)

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
