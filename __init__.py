# -*- coding: UTF-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Electronic Mail"

from electronic_mail import ElectronicMail, Mailbox, MailboxParent, \
        ReadUser, WriteUser, Header

from trytond.pool import Pool


def register():
    Pool.register(
        Mailbox,
        MailboxParent,
        ReadUser,
        WriteUser,
        ElectronicMail,
        Header,
        module='electronic_mail', type_='model',
    )
