import urllib2
import json
import time
import itertools
from wokkel.subprotocols import XMPPHandler
from wokkel.xmppim import AvailablePresence, Presence
from twisted.words.xish import domish

issues = {}
meta = {'RateLimitRemaining' : 60}
NS_MUC = 'http://jabber.org/protocol/muc'
NS_XHTML_IM = 'http://jabber.org/protocols/xhtml-im'
NS_XHTML_W3C = 'http://www.w3.org/1999/xhtml'

class IssueBot(XMPPHandler):

    def __init__(self, room, nick, password=None):
        XMPPHandler.__init__(self)

        self.room = room
        self.nick = nick
        self.password = password

    def connectionMade(self):
        self.send(AvailablePresence())

        # add handlers

        # join room
        pres = Presence()
        pres['to'] = self.room + '/' + self.nick
        x = pres.addElement((NS_MUC, 'x'))
        if not self.password is None:
            x.addElement('password', content = self.password)
        self.send(pres)
        self.notify("test...1")

    def notify(self, msgt):
        # build the messages
        text = [msgt]
        html = [msgt]
        # link = r"<a href='%s' name='%s'>%s</a>"
        
        # text.append('New commits in %s:\n' % data['repository']['url'])
        # html.append("New commits in " \
        #                 "<a href='%s'>%s</a>:<br/>" % \
        #                 (data['repository']['url'],
        #                  data['repository']['name']))
        # for c in data['commits']:
        #     text.append('%s | %s | %s\n' % (c['message'],
        #                                     c['author']['email'], 
        #                                     c['url']))
        #     ltxt = link % (c['url'], c['id'], c['id'][:7])
        #     html.append('%s | %s | %s<br />' % (c['message'],
        #                                         c['author']['email'],
        #                                         ltxt))
        msg = domish.Element((None, 'message'))
        msg['to'] = self.room
        msg['type'] = 'groupchat'
        msg.addElement('body', content=''.join(text))
        wrap = msg.addElement((NS_XHTML_IM, 'html'))
        body = wrap.addElement((NS_XHTML_W3C, 'body'))
        body.addRawXml(''.join(html))

        self.send(msg)

def pullApi(repo, state='open'):
    url = 'https://api.github.com/repos/' + repo + '/issues?state=' + state
    response = urllib2.urlopen(url)
    if response.info().getheader('Status') == '200 OK':
        return response.info().getheader('X-RateLimit-Remaining'),  json.load(response)
    else:
        print "[ERR ] Response Code != 200 OK, something's wrong."


def updateMeta(rlimit):
    meta['RateLimitRemaining'] = rlimit
    if rlimit <= 5:
        print "[WARN] Low Remaining Rate Limit - %i" % (rlimit)


def parseTime(timestring):
    tobj = time.strptime(timestring, "%Y-%m-%dT%H:%M:%SZ")
    return time.strftime("%s", tobj)


def newIssueFound(dct):
    tstamp = parseTime(dct['updated_at']) # As UNIX timestamp (epoch)
    issue_no = dct['number']
    issues[issue_no]['title'] = dct['title']
    issues[issue_no]['state'] = dct['state']
    try:
        issues[issue_no]['assignee'] = dct['assignee']['login']
    except TypeError:
        issues[issue_no]['assignee'] = "no one"
    issues[issue_no]['comments'] = dct['comments']
    issues[issue_no]['updated_at'] = tstamp
    issues[issue_no]['url'] = dct['html_url']
    return ["New Issue: \'%s\' (#%i, %s), assigned to %s, %i comments. URL: %s" % \
            (dct['title'], issue_no, dct['state'], issues[issue_no]['assignee'], \
                dct['comments'], dct['html_url'])]


def findIssueDelta(dct):
    retval = []
    issue_no = dct['number']
    if issues[issue_no]['title'] != dct['title']:
        rv = "Issue #%i updated: now called \'%s\' (was \'%s\')" % \
            (issue_no, dct['title'], issues[issue_no]['title'])
        retval.append(rv)
        issues[issue_no]['title'] = dct['title']
    if issues[issue_no]['state'] != dct['state']:
        rv = "Issue #%i updated: Issue is now %s (was %s)" % \
            (issue_no, dct['state'], issues[issue_no]['state'])
        retval.append(rv)
        issues[issue_no]['state'] = dct['state']
    try:
        if issues[issue_no]['assignee'] != dct['assignee']['login']:
            rv = "Issue #%i updated: now assigned to %s (was assigned to %s)" % \
                (issue_no, dct['assignee']['login'], issues[issue_no]['assignee'])
            retval.append(rv)
            issues[issue_no]['assignee'] = dct['assignee']['login']
    except TypeError:
        if issues[issue_no]['assignee'] != "no one":
            rv = "Issue #%i updated: now assigned to no one (was assigned to %s)" % \
                (issue_no, issues[issue_no]['assignee'])
            retval.append(rv)
            issues[issue_no]['assignee'] = "no one"
    if issues[issue_no]['comments'] != dct['comments']:
        rv = "Issue #%i updated: Gained %i comments (now at %i)" % \
            (issue_no, dct['comments'] - issues[issue_no]['comments'], dct['comments'])
        issues[issue_no]['comments'] = dct['comments']
    if retval != []:
        rv = "URL to Issue #%i: %s" % (issue_no, dct['html_url'])
        retval.append(rv)
    issues[issue_no]['updated_at'] = parseTime(dct['updated_at'])
    return retval


def processApiResult(element):
    retval = ""
    new = True
    dct = dict(element)
    issue_no = dct['number']
    try:
        issues[issue_no]
        new = False
    except KeyError:
        issues[issue_no] = {}
    if new:
        retval = newIssueFound(dct)
    else:
        tstamp = parseTime(dct['updated_at']) # As UNIX timestamp (epoch)
        if tstamp > issues[issue_no]['updated_at']: # Issue has updated, act on it
            retval = findIssueDelta(dct)
        else: # Issue has not updated, skip it.
            pass
    return retval


def main(repo, bot):
    # Initialize database with current data
    _, lst_open = pullApi(repo)
    rlimit, lst_closed = pullApi(repo, 'closed')
    updateMeta(rlimit)
    for element in itertools.chain(lst_open, lst_closed):
        processApiResult(element)
    # Database is set up. Now loop
    while(True):
        time.sleep(60)
        _, lst_open = pullApi(repo)
        rlimit, lst_closed = pullApi(repo, 'closed')
        updateMeta(rlimit)
        messages = []
        for element in itertools.chain(lst_open, lst_closed):
            messages.extend(processApiResult(element))
        for element in messages:
            bot.notify(element)
