#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Electronic Mail"
from __future__ import with_statement

import os
import base64
from sys import getsizeof
try:
    import hashlib
except ImportError:
    hashlib = None
    import md5
from datetime import datetime
from time import mktime
from email.utils import parsedate

from trytond.model import ModelView, ModelSQL, fields
from trytond.config import CONFIG
from trytond.transaction import Transaction


class Mailbox(ModelSQL, ModelView):
    "Mailbox"
    _name = "electronic_mail.mailbox"
    _description = __doc__

    name = fields.Char('Name', required=True)
    user = fields.Many2One('res.user', 'Owner')
    parents = fields.Many2Many(
             'electronic_mail.mailbox-mailbox',
             'parent', 'child' ,'Parents')
    subscribed = fields.Boolean('Subscribed')
    read_users = fields.Many2Many('electronic_mail.mailbox-read-res.user',
            'mailbox', 'user', 'Read Users')
    write_users = fields.Many2Many('electronic_mail.mailbox-write-res.user',
            'mailbox', 'user', 'Write Users')

Mailbox()


class MailboxParent(ModelSQL):
    'Mailbox - parent - Mailbox'
    _description = __doc__
    _name = 'electronic_mail.mailbox-mailbox'

    parent = fields.Many2One('electronic_mail.mailbox', 'Parent',
            ondelete='CASCADE', required=True, select=1)
    child = fields.Many2One('electronic_mail.mailbox', 'Child',
            ondelete='CASCADE', required=True, select=1)

MailboxParent()


class ReadUser(ModelSQL):
    'Electronic Mail - read - User'
    _description = __doc__
    _name = 'electronic_mail.mailbox-read-res.user'

    mailbox = fields.Many2One('electronic_mail.mailbox', 'Mailbox',
            ondelete='CASCADE', required=True, select=1)
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE',
            required=True, select=1)

ReadUser()


class WriteUser(ModelSQL):
    'Mailbox - write - User'
    _description = __doc__
    _name = 'electronic_mail.mailbox-write-res.user'

    mailbox = fields.Many2One('electronic_mail.mailbox', 'mailbox',
            ondelete='CASCADE', required=True, select=1)
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE',
            required=True, select=1)

WriteUser()


class ElectronicMail(ModelSQL, ModelView):
    "E-mail"
    _name = 'electronic_mail'
    _description = __doc__

    mailbox = fields.Many2One(
        'electronic_mail.mailbox', 'Mailbox', required=True)
    from_ = fields.Char('From')
    sender = fields.Char('Sender')
    to = fields.Char('To')
    cc = fields.Char('CC')
    bcc = fields.Char('BCC')
    subject = fields.Char('Subject')
    date = fields.DateTime('Date')
    message_id = fields.Char('Message-ID', help='Unique Message Identifier')
    in_reply_to = fields.Char('In-Reply-To')
    headers = fields.One2Many(
        'electronic_mail.header', 'electronic_mail', 'Headers')
    digest = fields.Char('MD5 Digest', size=32)
    collision = fields.Integer('Collision')
    email = fields.Function(fields.Binary('Email'), 'get_email', 'set_email')
    flag_seen = fields.Boolean('Seen')
    flag_answered = fields.Boolean('Answered')
    flag_flagged = fields.Boolean('Flagged')
    flag_draft = fields.Boolean('Draft')
    flag_recent = fields.Boolean('Recent')
    size = fields.Integer('Size')
    mailbox_owner = fields.Function(
        fields.Many2One('res.user', 'Owner'),
        'get_mailbox_owner', searcher='search_mailbox_owner')
    mailbox_read_users = fields.Function(
        fields.One2Many('res.user', None, 'Read Users'),
        'get_mailbox_users', searcher='search_mailbox_users')
    mailbox_write_users = fields.Function(
        fields.One2Many('res.user', None, 'Write Users'),
        'get_mailbox_users', searcher='search_mailbox_users')

    def default_collision(self):
        return 0

    def default_flag_seen(self):
        return False

    def default_flag_answered(self):
        return False

    def default_flag_flagged(self):
        return False

    def default_flag_recent(self):
        return False

    def get_mailbox_owner(self, ids, name):
        "Returns owner of mailbox"
        mails = self.browse(ids)
        return dict([(mail.id, mail.mailbox.user.id) for mail in mails])

    def get_mailbox_users(self, ids, name):
        assert name in ('mailbox_read_users', 'mailbox_write_users')
        res = {}
        for mail in self.browse(ids):
            if name == 'mailbox_read_users':
                res[mail.id] = [x.id for x in mail.mailbox['read_users']]
            else:
                res[mail.id] = [x.id for x in mail.mailbox['write_users']]
        return res

    def search_mailbox_owner(self, name, clause):
        return [('mailbox.user',) + clause[1:]]

    def search_mailbox_users(self, name, clause):
        return [('mailbox.' + name[8:],) + clause[1:]]

    def _get_email(self, electronic_mail):
        """
        Returns the email object from reading the FS
        :param electronic_mail: Browse Record of the mail
        """
        db_name = Transaction().cursor.dbname
        value = u''
        if electronic_mail.digest:
            filename = electronic_mail.digest
            if electronic_mail.collision:
                filename = filename + '-' + str(electronic_mail.collision)
            filename = os.path.join(
                CONFIG['data_path'], db_name, 
                'email', filename[0:2], filename)
            try:
                with open(filename, 'r') as file_p:
                    value =  file_p.read()
            except IOError:
                pass
        return value

    def get_email(self, ids, name):
        """Fetches email from the data_path as email object
        """
        result = { }
        for electronic_mail in self.browse(ids):
            result[electronic_mail.id] = base64.encodestring(
                self._get_email(electronic_mail)
                ) or False
        return result

    def set_email(self, ids, name, data):
        """Saves an email to the data path

        :param data: Email as string
        """
        if data is False or data is None:
            return
        db_name = Transaction().cursor.dbname
        # Prepare Directory <DATA PATH>/<DB NAME>/email
        directory = os.path.join(CONFIG['data_path'], db_name)
        if not os.path.isdir(directory):
            os.makedirs(directory, 0770)
        digest = self.make_digest(data)
        directory = os.path.join(directory, 'email', digest[0:2])
        if not os.path.isdir(directory):
            os.makedirs(directory, 0770)
        # Filename <DIRECTORY>/<DIGEST>
        filename = os.path.join(directory, digest)
        collision = 0

        if not os.path.isfile(filename):
            # File doesnt exist already
            with open(filename, 'w') as file_p:
                file_p.write(data)
        else:
            # File already exists, may be its the same email data
            # or maybe different. 

            # Case 1: If different: we have to write file with updated
            # Collission index

            # Case 2: Same file: Leave it as such
            with open(filename, 'r') as file_p:
                data2 = file_p.read()
            if data != data2:
                cursor = Transaction().cursor
                cursor.execute(
                    'SELECT DISTINCT(collision) FROM electronic_mail '
                    'WHERE digest = %s AND collision !=0 '
                    'ORDER BY collision', (digest,))
                collision2 = 0
                for row in cursor.fetchall():
                    collision2 = row[0]
                    filename = os.path.join(
                        directory, digest + '-' + str(collision2))
                    if os.path.isfile(filename):
                        with open(filename, 'r') as file_p:
                            data2 = file_p.read()
                        if data == data2:
                            collision = collision2
                            break
                if collision == 0:
                    collision = collision2 + 1
                    filename = os.path.join(
                        directory, digest + '-' + str(collision))
                    with open(filename, 'w') as file_p:
                        file_p.write(data)
        self.write(ids, {'digest': digest, 'collision': collision})

    def make_digest(self, data):
        """
        Returns a digest from the mail

        :param data: Data String
        :return: Digest
        """
        if hashlib:
            digest = hashlib.md5(data).hexdigest()
        else:
            digest = md5.new(data).hexdigest()
        return digest

    def create_from_email(self, mail, mailbox):
        """
        Creates a mail record from a given mail
        :param mail: email object
        :param mailbox: ID of the mailbox
        """
        header_obj = self.pool.get('electronic_mail.header')
        email_date = mail.get('date') and datetime.fromtimestamp(
                mktime(parsedate(mail.get('date'))))
        values = {
            'mailbox': mailbox,
            'from_': mail.get('from'),
            'sender': mail.get('sender'),
            'to': mail.get('to'),
            'cc': mail.get('cc'),
            'bcc': mail.get('bcc'),
            'subject': mail.get('subject'),
            'date': email_date,
            'message_id': mail.get('message-id'),
            'in_reply_to': mail.get('in-reply-to'),
            'email': mail.as_string(),
            'size': getsizeof(mail.as_string()),
            }
        create_id = self.create(values)
        header_obj.create_from_email(mail, create_id)
        return create_id

ElectronicMail()


class Header(ModelSQL, ModelView):
    "Header fields"
    _name = 'electronic_mail.header'
    _description = __doc__

    name = fields.Char('Name', help='Name of Header Field')
    value = fields.Char('Value', help='Value of Header Field')
    electronic_mail = fields.Many2One('electronic_mail', 'e-mail')

    def create_from_email(self, mail, mail_id):
        """
        :param mail: Email object
        :param mail_id: ID of the email from electronic_mail
        """
        for name, value in mail.items():
            values = {
                'electronic_mail':mail_id,
                'name':name,
                'value':value,
                }
            self.create(values)
        return True

Header()
