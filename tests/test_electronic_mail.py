#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Electronic Mail test suite"

import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))
import unittest

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view
from trytond.transaction import Transaction

USER_TYPES = ('owner_user_%s', 'read_user_%s', 'write_user_%s')


class ElectronicMailTestCase(unittest.TestCase):
    """
    Test Electronic Mail Module
    """

    def setUp(self):
        trytond.tests.test_tryton.install_module('electronic_mail')

        self.mailbox_obj = POOL.get('electronic_mail.mailbox')
        self.mail_obj = POOL.get('electronic_mail')
        self.header_obj = POOL.get('electronic_mail.header')
        self.user_obj = POOL.get('res.user')
        self.groups_obj = POOL.get('res.group')
        self.ir_model_data_obj = POOL.get('ir.model.data')

    def create_user(self, name):
        """
        Creates a new user and returns the ID
        """
        group_email_admin_id =  self.ir_model_data_obj.get_id(
            'electronic_mail', 'group_email_admin')
        group_email_user_id =  self.ir_model_data_obj.get_id(
            'electronic_mail', 'group_email_user')

        return self.user_obj.create(
            {
            'login': name,
            'name': name,
            'password': name,
            'groups': [('set', [group_email_admin_id, group_email_user_id])]
            })

    def create_users(self, no_of_sets=1):
        """
        A set of user is:
            1 Owner
            1 Read user
            1 Write User
        :return: List of tuple of the ID of three users
        """
        created_users = [ ]
        for iteration in xrange(1, no_of_sets + 1):
            created_users.append(
                tuple([
                    self.create_user(user_type % iteration) \
                        for user_type in USER_TYPES
                ])
            )
        return created_users

    def test0005views(self):
        '''
        Test views.
        '''
        self.assertRaises(Exception, test_view('electronic_mail'))

    def test0010mailbox_read_rights(self):
        '''
        Read access rights Test
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            # Create Users for testing access
            user_set_1, user_set_2 = self.create_users(no_of_sets=2)
            # Create a mailbox with a user set
            self.mailbox_obj.create(
                {
                    'name': 'Parent Mailbox',
                    'user': user_set_1[0],
                    'read_users': [('set', [user_set_1[1]])],
                    'write_users': [('set', [user_set_1[2]])],
                    })

            # Create a mailbox 2 with RW users of set 1 + set 2
            self.mailbox_obj.create(
                {
                    'name': 'Child Mailbox',
                    'user': user_set_2[0],
                    'read_users': [('set', [user_set_1[1], user_set_2[1]])],
                    'write_users': [('set', [user_set_1[2], user_set_2[2]])],
                    })

            # Directly test the mailboxes each user has access to
            expected_results = {
                user_set_1[0]: 1, user_set_2[0]: 1,
                user_set_1[1]: 2, user_set_2[1]: 1,
                user_set_1[2]: 2, user_set_2[2]: 1,
                USER: 2
                }
            for user_id, mailbox_count in expected_results.items():
                with Transaction().set_user(user_id):
                    self.assertEqual(
                        self.mailbox_obj.search([], count=True),
                        mailbox_count
                    )

            transaction.cursor.rollback()

    def test0020mail_create_access_rights(self):
        """
        Create access rights Test

        Create Three Users
            user_r, user_w, user_o

        Create a mailbox with write access to user_w and read access
        to user_r and owner as user_o

        Try various security combinations for create
        """
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            user_o, user_r, user_w = self.create_users(no_of_sets=1)[0]
            mailbox = self.mailbox_obj.create(
                {
                    'name': 'Mailbox',
                    'user': user_o,
                    'read_users': [('set', [user_r])],
                    'write_users': [('set', [user_w])],
                    })

            # Raise exception when writing a mail with the read user
            with Transaction().set_user(user_r):
                self.failUnlessRaises(
                    Exception, self.mail_obj.create,
                    ({
                        'from_': 'Test',
                        'mailbox': mailbox
                        },))

            # Creating mail with the write user
            with Transaction().set_user(user_w):
                self.assert_(
                    self.mail_obj.create({'from_': 'Test', 'mailbox': mailbox})
                )

            # Create an email as mailbox owner
            with Transaction().set_user(user_o):
                self.assert_(
                    self.mail_obj.create({'from_': 'Test', 'mailbox': mailbox})
                )

            transaction.cursor.rollback()

    def test0030_email_message_extraction(self):
        """The create from email functionality extracts info from
        an email.message. Test the extraction for multiple types
        """
        # 1: multipart/alternative
        message = MIMEMultipart('alternative')

        message['date'] = formatdate()
        message['Subject'] = "Link"
        message['From'] = "pythonistas@example.com"
        message['To'] = "trytonistas@example.com"
        text = """Hi!\nHow are you?\nHere is the link you wanted:
        http://www.python.org/
        http://www.tryton.org/
        """
        html = """\
        <html>
          <head></head>
          <body>
            <p>Hi!<br>
               How are you?<br>
               Here is the <a href="http://www.python.org">link</a> you wanted.
            </p>
          </body>
        </html>
        """
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        message.attach(part1)
        message.attach(part2)

        with Transaction().start(DB_NAME, USER, CONTEXT):
            mailbox = self.mailbox_obj.create(
                {
                    'name': 'Mailbox',
                    'user': USER,
                    'read_users': [('set', [USER])],
                    'write_users': [('set', [USER])],
                    })
            mail_id = self.mail_obj.create_from_email(message, mailbox)
            mail = self.mail_obj.browse(mail_id)

            self.assertEqual(mail.subject, message['Subject'])
            self.assertEqual(mail.from_, message['From'])
            self.assertEqual(mail.to, message['To'])


def suite():
    "Electronic mail test suite"
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ElectronicMailTestCase
        )
    )
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
