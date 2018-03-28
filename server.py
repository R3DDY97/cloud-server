#!/usr/bin/env python3
'''minimal cloud server'''

import os
import re
import json
# import base64
import asyncio
import mimetypes
# import binascii
from http import HTTPStatus
from email.utils import (formatdate, CRLF, EMPTYSTRING)
# import logging

METHODS = ("GET", "POST", "HEAD", "OPTIONS")
ROUTES = {method: {} for method in METHODS}
ALLOWED_DOMAINS = ("localhost:8000/index.html", )


def handle_post_methods(body, op_type, function):
    pass



# def body_handler(request, response, next_):    # server.res_status(response, 302)
#     # header = {"Content-Type: "text/html"}
#     # server.res_header(request, response, header)
#     content_type = request["header"].get("Content-Type", False)
#     if content_type:
#         request["body"] = json.loads(request["body"].decode())
#         # print(f'\n\n\n\n{request["body"]}\n\n\n')
#     return next_(request, response, next_)


def request_handler(request):
    response = {"protocol_version" : "HTTP/1.1", "header": {}}
    # response = "\nHTTP/1.1 200 OK\n\nHello, World!\n"
    next_ = create_next()
    return next_(request, response, next_)

def create_next():
    counter = 0
    def next_func(request, response, next_):
        nonlocal counter
        func = HANDLERS[counter]
        counter += 1
        return func(request, response, next_)
    return next_func

def static_file_handler(request, response, next_):
    if request["method"] == "GET" or (request["method"] == "POST" and request["path"]):
        if request["path"][-1] == "/":
            request["path"] += "index.html"
        filename = "static{}".format(request["path"])
        if not os.path.isfile(filename):
            return next_(request, response, next_)
        response["Content-Type"] = mimetypes.guess_type(request["path"])[0]
        with open(filename, "rb") as file_obj:
            res_body = file_obj.read()
        response["content"] = res_body
        return ok_200_handler(request, response)
    return next_(request, response, next_)


def route_handler(request, response, next_):    # server.res_status(response, 302)
    flag = 0
    routes = ROUTES[request["method"]]
    for regex, function in routes.items():
        answer = re.match(regex, request["path"])
        if answer:
            res_body = function(request, response, **answer.groupdict())
            flag = 1
            break
    if flag == 0:
        return next_(request, response, next_)
    if isinstance(res_body, bytes): # for redirect
        return res_body
    if res_body is not None:
        response["content"] = res_body.encode()
    return ok_200_handler(request, response)


def ok_200_handler(request, response):
    if "status" not in response:
        response["status"] = "200 OK"
    if "content" in response:
        response["header"]["Content-Length"] = str(len(response["content"]))
    response = response_handler(request, response)
    return response


def err_404_handler(request, response, next_):
    if "status" not in response:
        response["status"] = "404 Not Found"
    response = response_handler(request, response)
    return response


def response_handler(request, response):
    response["header"]["Date"] = formatdate(usegmt=True)
    response["header"]["Connection"] = "close"
    if "content" not in response:
        response["header"]["Content-Length"] = str(0)
    res = make_response(response)
    return res


def make_response(response):
    res = response["protocol_version"] + EMPTYSTRING + response["status"] + CRLF
    if response["header"]:
        for key, value in response["header"].items():
            res += "{0}: {1}{2}".format(key, value, CRLF)
    res += CRLF
    res_bytes = res.encode()
    if "content" in response:
        res_bytes += response["content"]
    return res_bytes

def res_status(response, status):
    status_dict = HTTPStatus.__dict__['_value2member_map_']
    status = status_dict.get(status, False)
    if status:
        response_phrase = status.name.replace("_", " ").title()
        response["status"] = "{0} {1}".format(status.value, response_phrase)
    else:
        raise ValueError("Invalid status code")



def get_query_content(request):
    path, query_params = request["path"].split("?")
    query_content = dict([query.split("=") for query in query_params.split("&")])
    return (path, query_content)

def header_parser(header_stream):
    req_line, *header_list = header_stream.split("\r\n")
    request = dict(zip(["method", "path", "http_version"], req_line.split()))

    if "?" in request["path"]:
        request["path"], request["query_content"] = get_query_content(request)

    header = dict([hdr.split(": ") for hdr in header_list])
    if "Cookie" in header:
        header["Cookie"] = dict([cookie.split("=") for cookie in header["Cookie"].split(";")])
    request["header"] = header
    return request


def body_parser(body_stream, content_type):
    if content_type == "application/json":
        parsed_request_body = json.loads(body_stream.decode())
    elif content_type == "application/x-www-form-urlencoded":
        parsed_request_body = query_parser(body_stream.decode())
    elif "multipart/form-data" in content_type:
        parsed_request_body = form_parser(body_stream, content_type)
    print(parsed_request_body)
    return parsed_request_body

def subhdr2dict(subhdr):
    subhdr = subhdr.decode().strip().replace('"', '')
    subhdr_lines = subhdr.split("Content-Disposition: form-data; ")[-1].split(CRLF)
    subhdr_dict = dict([i.split("=") for i in subhdr_lines[0].split("; ")])
    subhdr_dict.update(dict([subhdr_lines[1].split(":")]))
    return subhdr_dict

def form_parser(body_stream, content_type):
    boundary_value = content_type.split(";")[-1].split("=")[-1]
    boundary = "--{}".format(boundary_value).encode()
    # binary_body_stream = binascii.a2b_base64(body_stream)
    # decoded_body_stream = base64.encodebytes(body_stream)
    # print(binary_body_stream)
    # print(body_stream)
    # multiform_data = binary_body_stream.split(boundary)
    multiform_data = body_stream.split(boundary)[1:-1]
    # print(multiform_data)
    # print(len(multiform_data))
    data_list = [form.split((CRLF*2).encode()) for form in multiform_data] # list of (hdr, body)
    form_hdrs = [subhdr2dict(part[0]) for part in data_list]
    # form_body = [part[1] for part in data_list]
    form_dict = {}
    for index, hdr in enumerate(form_hdrs):
        form_dict[hdr.pop("filename")] = {"header": hdr, "body": data_list[index][1]}
    print(form_hdrs)
    # print(form_dict)
    return form_dict


def query_parser(query_string):
    query_str = query_string.split("&")
    query_dict = dict([query.split("=") for query in query_str])
    return query_dict


async def handle_message(reader, writer):
    # addr = writer.get_extra_info('peername')
    header = await reader.readuntil(b'\r\n\r\n')
    header_stream = header.decode().split("\r\n\r\n")[0]
    request = header_parser(header_stream)
    if "Content-Length" in request["header"]:
        con_len = request["header"]["Content-Length"]
        content_type = request["header"]["Content-Type"]
        body_stream = await reader.readexactly(int(con_len))
        request["body"] = body_parser(body_stream, content_type)
    response = request_handler(request)
    writer.write(response)
    await writer.drain()
    writer.close()


def execute_server(host='0.0.0.0', port=8000):
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(handle_message, host, port, loop=loop)
    server = loop.run_until_complete(coro)
    print('Serving on {}'.format(server.sockets[0].getsockname()))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("\nShutting down the server...\n")
    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()


# HANDLERS = [body_handler, static_file_handler, route_handler, err_404_handler]
HANDLERS = [static_file_handler, route_handler, err_404_handler]


if __name__ == '__main__':
    os.system("clear||cls")
    execute_server()
