""" Standalone webinterface for Openstack Swift. """
# -*- coding: utf-8 -*-
import os
import time
import hmac
import socket
from hashlib import sha1
from urllib.parse import urlparse
import urllib.request

from swiftclient import client
from keystoneauth1 import session
from keystoneauth1.identity import v3
from keystoneclient.v3 import client as ksclient

from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.urls import reverse

from mayx.forms import CreateContainerForm, PseudoFolderForm, LoginForm, AddACLForm
from mayx.utils import replace_hyphens, prefix_list, pseudofolder_object_list, get_temp_key, get_base_url, get_temp_url

import mayx

def login(request):
    """ 登录并存入session """
    OS_USER_DOMAIN_NAME = 'default'
    OS_PROJECT_DOMAIN_NAME = 'default'
    OS_AUTH_URL = 'http://controller:35357/v3'
    request.session.flush()
    form = LoginForm(request.POST or None)
    if form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        try:
            auth = v3.Password(auth_url=OS_AUTH_URL,
                   username=username,
                   password=password,
                   user_domain_name=OS_USER_DOMAIN_NAME,
                   project_name=username,#注册时要和用户名一起变
                   project_domain_name=OS_PROJECT_DOMAIN_NAME)
            keystone_session = session.Session(auth=auth)
            swift_conn = client.Connection(session=keystone_session)
            request.session['auth_token'] = swift_conn.get_auth()[1]
            request.session['storage_url'] = swift_conn.get_auth()[0].replace("controller",socket.gethostbyname("controller"))
            request.session['username'] = username
            return redirect(containerview)

        except Exception as err:
            messages.add_message(request, messages.ERROR, "登录失败:{0}".format(err))

    return render(request, 'login.html', {'form': form, })

def reg(request):
    """ 注册 """
    form = LoginForm(request.POST or None)
    if form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        try:
            OS_USER_DOMAIN_NAME = 'Default'
            OS_PROJECT_NAME = 'admin'
            OS_PROJECT_DOMAIN_NAME = 'Default'
            OS_AUTH_URL = 'http://controller:35357/v3'
            OS_USERNAME = "admin"
            OS_PASSWORD = "0728"
            """
            创建用户：openstack user create --domain default --password-prompt 用户名
            创建项目：openstack project create --domain default 用户名
            加入用户：openstack role add --project 用户名 --user 用户名 user
            """
            auth = v3.Password(auth_url=OS_AUTH_URL,
                username=OS_USERNAME,
                password=OS_PASSWORD,
                user_domain_name=OS_USER_DOMAIN_NAME,
                project_name=OS_PROJECT_NAME,
                project_domain_name=OS_PROJECT_DOMAIN_NAME)
            keystone_session = session.Session(auth=auth)
            keystone = ksclient.Client(session=keystone_session)
            userobj = keystone.users.create(name=username,password=password,domain="84bb9b93d2fd4951a8166597afaa3bbf")
            projectobj = keystone.projects.create(name=username,domain="84bb9b93d2fd4951a8166597afaa3bbf")
            keystone.roles.grant("21d951903d7347d98d0e40004d813da1",user=userobj,project=projectobj)
            messages.add_message(request, messages.INFO, "注册成功")
            return redirect(login)
        except Exception as err:
            messages.add_message(request, messages.ERROR, "注册失败:{0}".format(err))

    return render(request, 'reg.html', {'form': form, })

def containerview(request):
    """ 查看容器 """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    try:
        account_stat, containers = client.get_account(storage_url, auth_token)
    except client.ClientException as exc:
        if exc.http_status == 403:
            account_stat = {}
            containers = []
            base_url = get_base_url(request)
            messages.add_message(request, messages.ERROR, "没有列出权限")
        else:
            return redirect(login)
    except Exception as exc:
        messages.add_message(request, messages.ERROR, exc)
        return redirect(login)

    account_stat = replace_hyphens(account_stat)

    return render(request, 'containerview.html', {
        'account_stat': account_stat,
        'containers': containers,
        'session': request.session})


def create_container(request):
    """ 创建容器 """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    form = CreateContainerForm(request.POST or None)
    if form.is_valid():
        container = form.cleaned_data['containername']
        try:
            client.put_container(storage_url, auth_token, container)
            messages.add_message(request, messages.INFO,
                                 "容器已创建")
        except client.ClientException:
            messages.add_message(request, messages.ERROR, "拒绝访问")

        return redirect(containerview)

    return render(request, 'create_container.html', {})


def delete_container(request, container):
    """ 删除容器 """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    try:
        _m, objects = client.get_container(storage_url, auth_token, container)
        for obj in objects:
            client.delete_object(storage_url, auth_token,
                                 container, obj['name'])
        client.delete_container(storage_url, auth_token, container)
        messages.add_message(request, messages.INFO, "容器已删除")
    except client.ClientException:
        messages.add_message(request, messages.ERROR, "拒绝访问")

    return redirect(containerview)


def objectview(request, container, prefix=None):
    """ 查看对象 """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    try:
        meta, objects = client.get_container(storage_url, auth_token,
                                             container, delimiter='/',
                                             prefix=prefix)

    except client.ClientException:
        messages.add_message(request, messages.ERROR, "拒绝访问")
        return redirect(containerview)

    prefixes = prefix_list(prefix)
    pseudofolders, objs = pseudofolder_object_list(objects, prefix)
    base_url = get_base_url(request)
    account = storage_url.split('/')[-1]

    read_acl = meta.get('x-container-read', '').split(',')
    public = False
    required_acl = ['.r:*', '.rlistings']
    if [x for x in read_acl if x in required_acl]:
        public = True
    
    return render(request, "objectview.html", {
        'container': container,
        'objects': objs,
        'folders': pseudofolders,
        'session': request.session,
        'prefix': prefix,
        'prefixes': prefixes,
        'base_url': base_url,
        'account': account,
        'public': public})


def upload(request, container, prefix=None):
    """ 上传到swift """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    redirect_url = get_base_url(request)
    redirect_url += reverse('objectview', kwargs={'container': container, })

    swift_url = storage_url + '/' + container + '/'
    if prefix:
        swift_url += prefix
        redirect_url += prefix

    url_parts = urlparse(swift_url)
    path = url_parts.path

    max_file_size = 5 * 1024 * 1024 * 1024
    max_file_count = 1
    expires = int(time.time() + 15 * 60)
    key = get_temp_key(storage_url, auth_token)
    if not key:
        messages.add_message(request, messages.ERROR, "拒绝访问")
        if prefix:
            return redirect(objectview, container=container, prefix=prefix)
        else:
            return redirect(objectview, container=container)

    hmac_body = '%s\n%s\n%s\n%s\n%s' % (
        path, redirect_url, max_file_size, max_file_count, expires)
    signature = hmac.new(
        bytes(key, "utf-8"), bytes(hmac_body, "utf-8"), sha1).hexdigest()

    prefixes = prefix_list(prefix)

    return render(request, 'upload_form.html', {
        'swift_url': swift_url,
        'redirect_url': redirect_url,
        'max_file_size': max_file_size,
        'max_file_count': max_file_count,
        'expires': expires,
        'signature': signature,
        'container': container,
        'prefix': prefix,
        'prefixes': prefixes})


def download(request, container, objectname):
    """ 从swift下载 """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    url = mayx.utils.get_temp_url(storage_url, auth_token,
                                          container, objectname)
    if not url:
        messages.add_message(request, messages.ERROR, "拒绝访问")
        return redirect(objectview, container=container)

    return redirect(url)


def delete_object(request, container, objectname):
    """ 删除对象 """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    try:
        client.delete_object(storage_url, auth_token, container, objectname)
        messages.add_message(request, messages.INFO, "对象已删除")
    except client.ClientException:
        messages.add_message(request, messages.ERROR, "拒绝访问")
    if objectname[-1] == '/':  # deleting a pseudofolder, move one level up
        objectname = objectname[:-1]
    prefix = '/'.join(objectname.split('/')[:-1])
    if prefix:
        prefix += '/'
    return redirect(objectview, container=container, prefix=prefix)


def toggle_public(request, container):
    """ 设置公开权限 """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    try:
        meta = client.head_container(storage_url, auth_token, container)
    except client.ClientException:
        messages.add_message(request, messages.ERROR, "拒绝访问")
        return redirect(containerview)

    read_acl = meta.get('x-container-read', '')
    if '.rlistings' and '.r:*' in read_acl:
        read_acl = read_acl.replace('.r:*', '')
        read_acl = read_acl.replace('.rlistings', '')
        read_acl = read_acl.replace(',,', ',')
    else:
        read_acl += '.r:*,.rlistings'
    headers = {'X-Container-Read': read_acl, }

    try:
        client.post_container(storage_url, auth_token, container, headers)
    except client.ClientException:
        messages.add_message(request, messages.ERROR, "拒绝访问")

    return redirect(objectview, container=container)


def public_objectview(request, account, container, prefix=None):
    """ 公开版查看容器内容 """
    storage_url = settings.STORAGE_URL + account
    auth_token = b''
    try:
        _meta, objects = client.get_container(
            storage_url, auth_token, container, delimiter='/', prefix=prefix)

    except client.ClientException:
        messages.add_message(request, messages.ERROR, "拒绝访问")
        return redirect(containerview)

    prefixes = prefix_list(prefix)
    pseudofolders, objs = pseudofolder_object_list(objects, prefix)
    base_url = get_base_url(request)
    account = storage_url.split('/')[-1]

    return render(request, "publicview.html", {
        'container': container,
        'objects': objs,
        'folders': pseudofolders,
        'prefix': prefix,
        'prefixes': prefixes,
        'base_url': base_url,
        'storage_url': storage_url,
        'account': account})


def tempurl(request, container, objectname):
    """ 获得临时共享路径 """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    url = get_temp_url(storage_url, auth_token,
                       container, objectname, 7 * 24 * 3600)

    if not url:
        messages.add_message(request, messages.ERROR, "拒绝访问")
        return redirect(objectview, container=container)

    prefix = '/'.join(objectname.split('/')[:-1])
    if prefix:
        prefix += '/'
    prefixes = prefix_list(prefix)

    return render(request, 'tempurl.html', {
        'url': url,
        'account': storage_url.split('/')[-1],
        'container': container,
        'prefix': prefix,
        'prefixes': prefixes,
        'objectname': objectname,
        'session': request.session})

def viewfile(request, container, objectname):
    """ 预览文件 """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    url = get_temp_url(storage_url, auth_token,
                       container, objectname, 3600)
    filetype = client.head_object(storage_url, auth_token,
                       container, objectname)['content-type'].split("/")[0]

    if not url:
        messages.add_message(request, messages.ERROR, "拒绝访问")
        return redirect(objectview, container=container)

    prefix = '/'.join(objectname.split('/')[:-1])
    if prefix:
        prefix += '/'
    prefixes = prefix_list(prefix)

    return render(request, 'viewfile.html', {
        'filetype': filetype,
        'url': url,
        'account': storage_url.split('/')[-1],
        'container': container,
        'prefix': prefix,
        'prefixes': prefixes,
        'objectname': objectname,
        'session': request.session})

def create_pseudofolder(request, container, prefix=None):
    """ 创建文件夹 """
    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    form = PseudoFolderForm(request.POST)
    if form.is_valid():
        foldername = request.POST.get('foldername', None)
        if prefix:
            foldername = prefix + '/' + foldername
        foldername = os.path.normpath(foldername)
        foldername = foldername.strip('/')
        foldername += '/'

        content_type = 'application/directory'
        obj = None

        try:
            client.put_object(storage_url, auth_token,
                              container, foldername, obj,
                              content_type=content_type)
            messages.add_message(request, messages.INFO,
                                 "文件夹已创建")
        except client.ClientException:
            messages.add_message(request, messages.ERROR, "拒绝访问")

        if prefix:
            return redirect(objectview, container=container, prefix=prefix)
        return redirect(objectview, container=container)

    return render(request, 'create_pseudofolder.html', {
        'container': container, 'prefix': prefix})


def get_acls(storage_url, auth_token, container):
    """ 获得权限列表 """
    cont = client.head_container(storage_url, auth_token, container)
    readers = cont.get('x-container-read', '')
    writers = cont.get('x-container-write', '')
    return (readers, writers)


def remove_duplicates_from_acl(acls):
    """ 删除重复权限 """
    entries = acls.split(',')
    cleaned_entries = list(set(entries))
    acls = ','.join(cleaned_entries)
    return acls


def edit_acl(request, container):
    """ 编辑权限 """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    if request.method == 'POST':
        form = AddACLForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']

            (readers, writers) = get_acls(
                storage_url, auth_token, container)

            readers = remove_duplicates_from_acl(readers)
            writers = remove_duplicates_from_acl(writers)

            if form.cleaned_data['read']:
                readers += ",%s" % username

            if form.cleaned_data['write']:
                writers += ",%s" % username

            headers = {'X-Container-Read': readers,
                       'X-Container-Write': writers}
            try:
                client.post_container(
                    storage_url, auth_token, container, headers)
                message = "权限已更新"
                messages.add_message(request, messages.INFO, message)
            except client.ClientException:
                message = "权限更新失败"
                messages.add_message(request, messages.ERROR, message)

    if request.method == 'GET':
        delete = request.GET.get('delete', None)
        if delete:
            users = delete.split(',')

            (readers, writers) = get_acls(storage_url, auth_token, container)

            new_readers = ""
            for element in readers.split(','):
                if element not in users:
                    new_readers += element
                    new_readers += ","

            new_writers = ""
            for element in writers.split(','):
                if element not in users:
                    new_writers += element
                    new_writers += ","

            headers = {'X-Container-Read': new_readers,
                       'X-Container-Write': new_writers}
            try:
                client.post_container(storage_url, auth_token,
                                      container, headers)
                message = "权限已移除"
                messages.add_message(request, messages.INFO, message)
            except client.ClientException:
                message = "权限更新失败"
                messages.add_message(request, messages.ERROR, message)

    (readers, writers) = get_acls(storage_url, auth_token, container)

    acls = {}

    if readers != "":
        readers = remove_duplicates_from_acl(readers)
        for entry in readers.split(','):
            acls[entry] = {}
            acls[entry]['read'] = True
            acls[entry]['write'] = False

    if writers != "":
        writers = remove_duplicates_from_acl(writers)
        for entry in writers.split(','):
            if entry not in acls:
                acls[entry] = {}
                acls[entry]['read'] = False
            acls[entry]['write'] = True

    public = False
    if acls.get('.r:*', False) and acls.get('.rlistings', False):
        public = True

    if request.is_secure():
        base_url = "https://%s" % request.get_host()
    else:
        base_url = "http://%s" % request.get_host()

    return render(request, 'edit_acl.html', {
        'container': container,
        'account': storage_url.split('/')[-1],
        'session': request.session,
        'acls': acls,
        'public': public,
        'base_url': base_url})
        
def copysource(request, container, objectname):
    """ 复制文件 - 源 """
    request.session['copy_source'] = container + "/" + objectname
    request.session['copy_type'] = 0
    messages.add_message(request, messages.INFO, "复制成功！请在目标位置点击红色按钮中的粘贴")
    prefix = '/'.join(objectname.split('/')[:-1])
    if prefix:
        prefix += '/'
    return redirect(objectview, container=container, prefix=prefix)
    
def movesource(request, container, objectname):
    """ 剪切文件 - 源 """
    request.session['copy_source'] = container + "/" + objectname
    request.session['copy_type'] = 1
    messages.add_message(request, messages.INFO, "剪切成功！请在目标位置点击红色按钮中的粘贴")
    prefix = '/'.join(objectname.split('/')[:-1])
    if prefix:
        prefix += '/'
    return redirect(objectview, container=container, prefix=prefix)
    
def copydest(request, container, prefix=None):
    """ 粘贴文件 - 目标 """
    
    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    
    dcontainer, dname = request.session.get('copy_source', '/').split("/",1)
    
    if prefix:
        destination = container + "/" + prefix + dname.split('/')[-1]
    else:
        destination = container + "/" + dname.split('/')[-1]
    print(destination)
    
    try:
        client.copy_object(storage_url, auth_token, container=dcontainer, name=dname, destination=destination)
        if request.session.get('copy_type', '0') == 1:
            client.delete_object(storage_url, auth_token, container=dcontainer, name=dname)
        messages.add_message(request, messages.INFO, "粘贴成功！")
    except client.ClientException:
        messages.add_message(request, messages.ERROR, "粘贴失败")
    del request.session['copy_source']
    del request.session['copy_type']
    if prefix:
        return redirect(objectview, container=container, prefix=prefix)
    else:
        return redirect(objectview, container=container)