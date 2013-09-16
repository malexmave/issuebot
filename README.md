issuebot
========

Issuebot is an XMPP bot that notifies multi-user chat rooms (MUCs) of
changes to Issues on a GitHub-Project

It uses the [GitHub API](http://developer.github.com) to get push 
notifications of repository changes.

## License

This code is licensed under the [GPLv3](http://www.gnu.org/licenses/gpl.html).
See `LICENSE.txt` for details.
Portions of this code are based on Code by Jack Moffitt <jack@metajack.im> from
the [CommitBot](https://github.com/metajack/commitbot)-Project, (c) 2008.

## Dependencies

* [Twisted](http://www.twistedmatrix.com) 8.1.x or later
* [Wokkel](http://wokkel.ik.nu) 0.4 or later

Note that on Ubuntu/Debian systems Twisted is split into various
pieces.  You will want:

* python-twisted-words
* python-twisted-names

in addition to the normal Twisted package.

## Usage

Copy `issuebot.tac.example` to `issuebot.tac` changing the jabber_id,
password, room, repo, and bot_name to something appropriate.  Then
launch it with `twistd`.

    twistd -y issuebot.tac

If everything worked fine, a new user should have joined your MUC.