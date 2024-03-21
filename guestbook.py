#! /usr/bin/env python3

import sys
import os
#import sqlite3
#import zipfile
import io
#import json
#import glob
#import pathlib
import types
import time
#import re

# requirements
#import captcha # https://pypi.org/project/captcha/
from captcha.image import ImageCaptcha

#import psycopg2 # postgreSQL https://pypi.org/project/psycopg2/



# global config
# user has 1 minute to solve captcha
captcha_seconds = 60
#captcha_seconds = 600 # 10 min
message_size_max = 3_000_000 # 3 MB
attachment_size_max = 6_000_000 # 6 MB
guestbook_size_max = 500_000_000 # 500 MB



# global state
is_cgi = False

captcha_time_slot = str(round(time.time() / captcha_seconds + 0.5)).encode("ascii")
captcha_hash_seed = b"asdfguessmehasdufawewohahahhaha" + captcha_time_slot



def html_entities_encode(s, quote=True):
    """
    based on html.escape in python3-3.11.7/lib/python3.11/html/__init__.py

    Replace special characters "&", "<" and ">" to HTML-safe sequences.
    If the optional flag quote is true (the default), the quotation mark
    characters, both double quote (") and single quote (') characters are also
    translated.
    """
    s = s.replace("&", "&amp;") # Must be done first!
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    if quote:
        s = s.replace('"', "&quot;")
        s = s.replace('\'', "&#x27;")
    return s


def show_start_cgi(message=None, error=None):

    import base64

    def write(line=b""):
        sys.stdout.buffer.write(line + b"\n")

    # if we dont flush sys.stdout here, then sys.stdout.buffer is written first
    #sys.stdout.flush()
    #sys.stdout.buffer.write(b'<img src="data:image/png,base64">')
    #sys.stdout.buffer.flush()

    write(b"Status: 200")
    write(b"Content-Type: text/html")
    write()

    if message:
        message = html_entities_encode(message)
        message = message.encode("utf8", errors="replace")
    else:
        message = b"message"

    if error:
        error = html_entities_encode(error)
        error = error.encode("utf8", errors="replace")

    import random
    # 1 and 7 are very similar...
    captcha_text = "".join(random.choices("0123456789", k=8))

    import hashlib
    captcha_hash = hashlib.sha256(captcha_hash_seed + captcha_text.encode("ascii")).hexdigest().encode("ascii")

    captcha_png_bytes = ImageCaptcha(240, 60).generate(captcha_text).getvalue()

    write(b'<!doctype html>')
    write(b'<html>')
    write(b'<head>')
    write(b'<meta charset="utf-8">')
    write(b'<title>guestbook</title>')
    write(b'<style>')
    #write(b'* { font-family: monospace; font-size: 100%; font-weight: normal; }')
    write(b'input { border: solid 1px black; padding: 0.5em; }')
    write(b'textarea { padding: 0.5em; border: none; overflow: auto; overflow-y: scroll; outline: none; box-shadow: none; resize: none; scrollbar-width: auto; }')
    # invert colors in darkmode. this works only with chromium + darkreader, not with tor-browser + darkreader
    write(b'@media screen { :root[data-darkreader-mode="dynamic"] .darkmode-invert { filter: invert(); } }')
    write(b'</style>')
    write(b'</head>')
    write(b'<body style="margin: 0; padding: 0; ">')
    #write(b'<h1>guestbook</h1>')
    write(b'<form method="post" enctype="multipart/form-data" accept-charset="UTF-8" style="display: flex; flex-direction: column; height: 100vh; overflow: hidden; ">')
    #write(b'<textarea style="width:100%;height:100%; flex-grow:1" name="message">message</textarea>')
    write(b'<textarea style="flex-grow:1" name="message">' + message + b'</textarea>')
    if error:
        write(b'<div class="error" style="text-align: center">error: ' + error + b'</div>')
    #write(b'<div>debug: captcha_hash_seed = ' + captcha_hash_seed + b'</div>')
    write(b'<div style="display:flex; justify-content: center; align-items: center;">')
    write(b'  <img class="darkmode-invert" style="margin: 0 1em" src="data:image/png;base64,' + base64.b64encode(captcha_png_bytes) + b'">')
    write(b'  <input style="margin: 0 1em" name="captcha" value="captcha">')
    write(b'  <input style="margin: 0 1em" name="attachment" type="file">')
    write(b'  <input style="margin: 0 1em" type="submit" value="send">')
    write(b'</div>')
    write(b'<input type="hidden" name="captcha-hash" value="' + captcha_hash + b'">')
    write(b'</form>')
    write(b'</body>')
    write(b'</html>')

    sys.exit()



def error(msg):
    raise Exception(msg)



def error_cgi(msg, status=400):
    print(f"Status: {status}")
    print("Content-Type: text/plain")
    print()
    print("error: " + msg)
    sys.exit()



def main_cgi():

    import urllib.parse

    #import os; _bytes = os.read(3, 100); error(repr(_bytes))

    # CONTENT_TYPE

    # debug
    #import json; error(json.dumps(dict(os.environ), indent=2))

    message = None
    attachment_filename = None
    attachment_bytes = None
    attachment_size = 0
    captcha = None
    captcha_hash = None

    if os.environ.get("REQUEST_METHOD") == "GET":
        show_start_cgi()
        return
        """
        query_string = os.environ.get("QUERY_STRING")
        #query_list = urllib.parse.parse_qsl(query_string, keep_blank_values=True)
        query_dict = urllib.parse.parse_qs(query_string, keep_blank_values=True)
        def get_arg(key):
            return query_dict.get(key, [None])[0]
        message = get_arg("message")
        """

    if os.environ.get("REQUEST_METHOD") != "POST":
        error("only GET and POST requests are supported")

    # method == post

    #query_string = sys.stdin.read()
    #query_bytes = sys.stdin.buffer.read()
    # https://github.com/defnull/multipart
    import multipart
    wsgi_env = dict(os.environ)
    wsgi_env["wsgi.input"] = sys.stdin.buffer
    try:
        # IndexError @ len_first_line = len(lines[0])
        # https://github.com/defnull/multipart/issues/47
        #forms, files = multipart.parse_form_data(os.environ)
        forms, files = multipart.parse_form_data(wsgi_env)
    except Exception as exc:
        import traceback
        error(str(exc) + "\n\n" + traceback.format_exc())

    if "attachment" in files:
        attachment = files["attachment"]
        attachment_filename = os.path.basename(attachment.filename)
        attachment_bytes = attachment.file.getvalue()
        attachment_size = len(attachment_bytes)
        attachment = None
        if attachment_size > attachment_size_max:
            error(f"attachment is too large. max: {attachment_size_max} bytes")
    files = None

    def get_arg(key):
        return forms.get(key, None)

    message = get_arg("message")
    captcha = get_arg("captcha")
    captcha_hash = get_arg("captcha-hash")

    if len(message) > message_size_max:
      error(f"message is too large. max: {message_size_max} bytes")

    import hashlib
    captcha_hash_actual = hashlib.sha256(captcha_hash_seed + captcha.encode("ascii", errors="replace")).hexdigest()

    if captcha_hash != captcha_hash_actual:
        show_start_cgi(message, "bad captcha. please retry")

    # good captcha
    # write to database

    # debug postgresql database
    # sudo -u lighttpd psql

    import psycopg2

    conn = psycopg2.connect(
        database="lighttpd",
        #host="127.0.0.1",
        user="lighttpd",
        #password="",
        #port=5432,
    )

    cursor = conn.cursor()

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS guestbook ("
        "time INTEGER,"
        "message_size INTEGER,"
        "message TEXT,"
        "attachment_filename TEXT,"
        "attachment_size INTEGER,"
        "attachment_bytes BYTEA," # https://www.postgresql.org/docs/7.4/jdbc-binary-data.html
        "captcha_hash TEXT UNIQUE"
        ")"
    )

    # check size of table vs size limit
    sql_query = "select sum(message_size) + sum(attachment_size) from guestbook"
    cursor.execute(sql_query)
    guestbook_size = cursor.fetchone()[0]
    if guestbook_size > guestbook_size_max:
        error("guestbook is full. maybe retry in a few days")

    import time

    sql_query = (
        "INSERT INTO guestbook ("
        "time, message_size, message,"
        "attachment_filename, attachment_size, attachment_bytes,"
        "captcha_hash"
        ") VALUES (%s, %s, %s, %s, %s, %s, %s)"
    )

    sql_args = (
        int(time.time()), len(message), message,
        attachment_filename, attachment_size, attachment_bytes,
        captcha_hash,
    )

    try:
        cursor.execute(sql_query, sql_args)
    except psycopg2.errors.UniqueViolation:
        error("captcha was already used")

    conn.commit() # actually write data

    conn.close()

    #error("ok")
    # def error
    status = 200
    print(f"Status: {status}")
    print("Content-Type: text/plain")
    print()
    print("ok. your message was sent")
    sys.exit()

    # TODO render the guestbook entries, protected by a password

    """
    # debug
    cursor.execute("SELECT time, message, attachment_filename FROM guestbook")
    message_list = cursor.fetchall()

    def format_timestamp(t):
        return time.strftime("%F %T %z", time.gmtime(t))

    # debug
    message_list = [(format_timestamp(t), m, an) for (t, m, an) in message_list]
    import json
    error(json.dumps(message_list, indent=2))
    """



def main():

    global data_dir
    global is_cgi
    global error
    global unpack_zipfiles

    # see also https://github.com/technetium/cgli/blob/main/cgli/cgli.py

    if os.environ.get("GATEWAY_INTERFACE") == "CGI/1.1":
        is_cgi = True
        error = error_cgi

    if is_cgi:
        return main_cgi()

    raise NotImplementedError("no cli. cli only")
    #return main_cli()



if __name__ == "__main__":
    main()
    sys.exit()
