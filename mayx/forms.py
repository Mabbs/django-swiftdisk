""" 表单提交规则 """
# -*- coding: utf-8 -*-
from django import forms


class CreateContainerForm(forms.Form):
    """ 容器名 """
    containername = forms.CharField(max_length=100)


class AddACLForm(forms.Form):
    """ 权限 """
    username = forms.CharField(max_length=100)
    read = forms.BooleanField(required=False)
    write = forms.BooleanField(required=False)


class PseudoFolderForm(forms.Form):
    """ 创建文件夹 """
    foldername = forms.CharField(max_length=100)


class LoginForm(forms.Form):
    """ 登录 """
    username = forms.CharField(max_length=100)
    password = forms.CharField(widget=forms.PasswordInput)
