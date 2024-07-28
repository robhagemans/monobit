"""
monobit.storage.containers.email - files embedded in email messages

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT

Based on Python documentation examples at
https://docs.python.org/3/library/email.examples.html

> Thanks to Matthew Dixon Cowles for the original inspiration and examples.

> © Copyright 2001-2024, Python Software Foundation.
> This page is licensed under the Python Software Foundation License Version 2.
> Examples, recipes, and other code in the documentation are additionally
> licensed under the Zero Clause BSD License.
> See https://docs.python.org/license.html for more information.
"""

import email
from email.message import EmailMessage
from email.policy import SMTP, default
import mimetypes
from pathlib import Path

from ..magic import FileFormatError
from ..base import containers
from ..containers import FlatFilterContainer


@containers.register(
    name='email',
    patterns=('*.eml', '*.msg'),
)
class EmailContainer(FlatFilterContainer):

    def decode(self, name):
        """
        Decode files from email attachments.
        """
        return super().decode(name)

    def encode(
            self, name, *,
            sender:str='me@here',
            recipient:str='you@there',
            subject:str='Files',
        ):
        """
        Encode files to email attachments. Only the email parameters of the last file wrtten have an effect.

        sender: email From field
        recipient: email To field
        subject: email Subject
        """
        return super().encode(
            name,
            sender=sender,
            recipient=recipient,
            subject=subject,
        )

    @classmethod
    def encode_all(cls, data, outstream):
        if not data:
            return
        # Create the message
        msg = EmailMessage()
        msg.preamble = 'This is a multi-part message in MIME format.\n'
        for filename, filedict in data.items():
            msg['Subject'] = filedict['subject']
            msg['To'] = filedict['recipient']
            msg['From'] = filedict['sender']
            filedata = filedict.pop('outstream').getvalue()
            # Guess the content type based on the file's extension.  Encoding
            # will be ignored, although we should check for simple things like
            # gzip'd or compressed files.
            ctype, encoding = mimetypes.guess_type(filename)
            if ctype is None or encoding is not None:
                # No guess could be made, or the file is encoded (compressed), so
                # use a generic bag-of-bits type.
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            msg.add_attachment(
                filedata, maintype=maintype, subtype=subtype, filename=filename
            )
        # Now send or store the message
        outstream.write(msg.as_bytes(policy=SMTP))

    @classmethod
    def decode_all(cls, instream):
        msg = email.message_from_binary_file(instream, policy=default)
        data = {}
        counter = 1
        for part in msg.walk():
            # multipart/* are just containers
            if part.get_content_maintype() == 'multipart':
                continue
            # Applications should really sanitize the given filename so that an
            # email message can't be used to overwrite important files
            filename = part.get_filename()
            if not filename:
                ext = mimetypes.guess_extension(part.get_content_type())
                if not ext:
                    # Use a generic bag-of-bits extension
                    ext = '.bin'
                filename = f'part-{counter:03d}{ext}'
            counter += 1
            data[filename] = part.get_payload(decode=True)
        return data
