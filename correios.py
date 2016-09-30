#!/usr/bin/env python3
# coding=utf-8

import os
import configparser
from datetime import datetime
import requests
import json
import smtplib
from email.mime.text import MIMEText

config = configparser.ConfigParser()
config.read(os.path.dirname(__file__) + "/config.ini")
quiet = config.getboolean("misc", "quiet", fallback=True)
debug = config.getboolean("misc", "debug", fallback=False)
filename = os.path.dirname(__file__) + "/" + config.get("misc", "filename")


def main():
    data = get_old_data_from_file()

    if not quiet:
        print("Fetching data from Correios...")
    codes = config.get("correios", "codes").split()
    result = get_data_from_correios(codes)
    if result is None:
        return
    if debug:
        print(json.dumps(result, indent=4))

    for objeto in result["objeto"]:
        numero = objeto["numero"]
        evento = objeto["evento"][0]
        this_update = datetime.strptime(evento["criacao"], "%d%m%Y%H%M%S")
        if numero in data:
            last_update = datetime.fromtimestamp(data[numero]["last_update"])
            if last_update >= this_update:
                # this is an old event, so ignore it and continue with the next one
                continue
        else:
            data[numero] = {"events": []}
        # notify about new event
        notify(numero, evento)
        data[numero]["last_update"] = this_update.timestamp()
        data[numero]["events"].append(evento)
    # remember all new events, so we don't notify about them again
    save_data_to_file(data)


def notify(code, evento):
    if not quiet:
        print("We have a new event! Notify about it...")
    event = {
        "code": code,
        "date": datetime.strptime(evento["criacao"], "%d%m%Y%H%M%S"),
        "description": evento["descricao"],
        "from_name": evento["unidade"]["local"],
        "from_lat": evento["unidade"]["endereco"]["latitude"],
        "from_lon": evento["unidade"]["endereco"]["longitude"]
    }
    if "destino" in evento:
        event["to_name"] = evento["destino"][0]["local"]
        endereco = evento["destino"][0]["endereco"]
        if "latitude" in endereco and "longitude" in endereco:
            event["to_lat"] = endereco["latitude"]
            event["to_lon"] = endereco["longitude"]
    send_email(event)


def get_old_data_from_file():
    if os.access(filename, os.R_OK):
        with open(filename, 'r') as outfile:
            return json.load(outfile)
    else:
        return {}


def save_data_to_file(data):
    with open(filename, 'w') as outfile:
        json.dump(data, outfile, indent=4)


def get_data_from_correios(objetos):
    request_xml = '''
    <rastroObjeto>
        <usuario>MobileXect</usuario>
        <senha>DRW0#9F$@0</senha>
        <tipo>L</tipo>
        <resultado>U</resultado>
        <objetos>%s</objetos>
        <lingua>101</lingua>
        <token>QTXFMvu_Z-6XYezP3VbDsKBgSeljSqIysM9x</token>
    </rastroObjeto>
    ''' % ''.join(objetos)  # for full history use: <resultado>L</resultado>

    url = 'http://webservice.correios.com.br/service/rest/rastro/rastroMobile'
    headers = {
        'Content-Type': 'application/xml',
        'Accept': 'application/json',
        'User-Agent': 'Dalvik/1.6.0 (Linux; U; Android 4.2.1; LG-P875h Build/JZO34L)'
    }
    try:
        result = requests.post(url, data=request_xml, headers=headers).text
    except TimeoutError as e:
        if not quiet:
            print(e)
        return None
    try:
        return json.loads(result)
    except ValueError as e:
        if not quiet:
            print(e)
        return None


def send_email(event):
    if not quiet:
        print("Sending email...")
    subject = "[%(code)s] %(description)s" % event
    if debug:
        print("Subject: %s" % subject)
    body = "%(date)s\n\n\nFrom\n%(from_name)s" % event
    if "from_lat" in event and "from_lon" in event:
        body += "\nhttp://www.openstreetmap.org/?mlat=%(from_lat)s&mlon=%(from_lon)s" % event
    if "to_name" in event:
        body += "\n\nTo\n%(to_name)s" % event
        if "to_lat" in event and "to_lon" in event:
            body += "http://www.openstreetmap.org/?mlat=%(to_lat)s&mlon=%(to_lon)s" % event
    if debug:
        print("Body: %s" % body)

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = config.get('email', 'from')
    msg['To'] = config.get('email', 'to')

    s = smtplib.SMTP('localhost')
    s.sendmail(config.get('email', 'from'), config.get('email', 'to'), msg.as_string())
    s.quit()


if __name__ == '__main__':
    main()
