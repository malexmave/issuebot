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
password, room, repos (you can enter more than one repository, please
format them as a python list), and bot_name to something appropriate. 
Then launch it with `twistd`.

    twistd -y issuebot.tac

If everything worked fine, a new user should have joined your MUC.

## Experts

If you want a high update frequency or monitor a high number of repositories,
please consider adding an OAuth key to increase your API limit from 60 / hour
to 5000 / hour. Set the token into the respective variable in the tac-file.

Instructions on how to obtain such a token can be found on the 
[GitHub developer site](https://developer.github.com/guides/getting-started/#authentication)
(look for the section on OAuth and follow the instructions, pasting the generated 
token into the variable as a String). This is entirely optional, but please note 
that GitHub may be angry if you exceed your Rate Limit, and the bot may crash.