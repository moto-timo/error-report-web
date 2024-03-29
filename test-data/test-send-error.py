#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

# test/example script for sending data to error-report-web

import urllib.request, urllib.error, urllib.parse
import sys

def send_data (url, data_file):
        print("===== Sending =====")
        print(data_file + " to " + url)

        with open(data_file) as f:
            data = f.read()

        data = urllib.parse.urlencode({'data': data }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={'Content-type': 'application/json'})
        try:
            response = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            response = e

        print("===== Response =====")
        print(response.read())

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Please specify a url and data file\nUsage:\n\t test-send-error.py <url> <json data file path> \nExample:\n\t test-send-error.py http://localhost:8000/ClientPost/JSON/ ./test-payload.json\n")
    else:
        send_data(sys.argv[1], sys.argv[2])

    sys.exit(0)
