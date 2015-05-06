#!/bin/bash

# Copyright (c) 2015 Florian Brucker (mail@florianbrucker.de).
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# Script to create Coba-specific users and groups for testing purposes. See
# also ``remove_test_users.sh`` for removing them again. The users have no home
# directories and cannot login.

read -p "Really create test users and groups (y/n)? " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    sudo useradd --comment "Test user A for the Coba backup system" \
                 --shell /sbin/nologin \
                 --user-group \
                 coba_test_a
    sudo useradd --comment "Test user B for the Coba backup system" \
                 --shell /sbin/nologin \
                 --user-group \
                 coba_test_b
    sudo usermod -a -G coba_test_b coba_test_a
    sudo usermod -a -G coba_test_a coba_test_b
    echo Created test users and groups.
else
    echo Not creating test users and groups.
fi

