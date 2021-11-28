from lektor.pluginsystem import Plugin
from lektor.context import site_proxy, get_ctx
import csv
import os
from collections import defaultdict

from werkzeug.urls import url_parse
from markupsafe import escape

NOFOLLOW_LINK_PREFIX = '!'

import sys


if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding('utf8')
else:
    unicode = str

def get_drive_url(path):
    drive_paths = site_proxy.databags.get_bag('drivepaths')
    p = path
    if '/seminarContent' in path and not path.startswith('/seminarContent/'):
        p = p[p.find('/seminarContent'):]

    if '/seminarContent' in path and p not in drive_paths:
        raise ValueError("Path not in Google Drive: {}".format(p))
    elif '/seminarContent' not in path and p not in drive_paths:
        return p

    ident = drive_paths[p]

    return "https://drive.google.com/file/d/{}/view?usp=sharing".format(ident)

class LinkMixin(object):
    def link(self, link, title, text):
        nofollow = link.startswith(NOFOLLOW_LINK_PREFIX)
        link = link.lstrip(NOFOLLOW_LINK_PREFIX)
        
        if self.record is not None:
            url = url_parse(link)
            if not url.scheme:
                link = self.record.url_to('!' + link,
                                          base_url=get_ctx().base_url)
        if '/seminarContent' in link:
            link = get_drive_url(link)
        link = escape(link)

        if not title:
            if nofollow:
                return '<a href="%s" rel="nofollow">%s</a>' % (link, text) 
            else:
                return '<a href="%s">%s</a>' % (link, text)
        title = escape(title)
        if nofollow:
            return '<a href="%s" title="%s" rel="nofollow">%s</a>' % (link, title, text)
        else:
            return '<a href="%s" title="%s">%s</a>' % (link, title, text)

class PapersTable:

    def __init__(self, table_title, table_data):
        self.table_title = table_title
        self.table_data = table_data

class ConferenceTemplatePlugin(Plugin):
    name = 'FAA Human Factors Jinja Template Functions'
    description = 'Adds specific or generalized template functions to Jinja.'

    def on_markdown_config(self, config, **extra):
        config.renderer_mixins.append(LinkMixin)

    def paper_csv(self, paper_attachments):
        relevant_attachments = []
        for attach in paper_attachments:
            if 'papers.csv' in attach.attachment_filename:
                pt = PapersTable("Accepted Papers", self._parse_csv(attach.attachment_filename))
                relevant_attachments.append((3,pt))
            elif 'tutorials.csv' in attach.attachment_filename:
                pt = PapersTable("Tutorials", self._parse_csv(attach.attachment_filename))
                relevant_attachments.append((2,pt))
            elif 'keynotes.csv' in attach.attachment_filename:
                pt = PapersTable("Keynotes", self._parse_csv(attach.attachment_filename))
                relevant_attachments.append((1,pt))
        # Keynotes, then tutorials, then papers
        relevant_attachments.sort()
        return [x[1] for x in relevant_attachments]
        

    def _parse_csv(self, csv_filename):
        with open(csv_filename, "r", encoding="utf8") as f:
            reader = csv.DictReader(f)
            all_items = [row for row in reader]
        if sys.version_info < (3, 0):
            return [{unicode(k, 'utf-8', errors='ignore'): unicode(v, 'utf-8', errors='ignore') for k,v in row.iteritems()} for row in all_items]
        else:
            return [{k: v for k,v in row.items()} for row in all_items]

    def has_abstracts_file(self, papers_attachment):
        return any(['abstracts_file' in row and row['abstracts_file'] for row in papers_attachment])

    def has_presentations(self, papers_attachment):
        return any(['presentation' in row and row['presentation'] for row in papers_attachment])

    def has_papers(self, papers_attachment):
        return any(['paper' in row and row['paper'] for row in papers_attachment])

    def has_videos(self, papers_attachment):
        return any(['video' in row and row['video'] for row in papers_attachment])

    def has_best(self, papers_attachment):
        return any(['best' in row and row['best'] for row in papers_attachment])

    def has_themes(self, papers_attachment):
        return any(['theme' in row and row['theme'] for row in papers_attachment])
    
    def on_setup_env(self, **extra):
        self.env.jinja_env.globals.update(paper_csv=self.paper_csv,
                                          has_abstracts_file=self.has_abstracts_file,
                                          has_presentations=self.has_presentations,
                                          has_papers=self.has_papers,
                                          has_videos=self.has_videos,
                                          has_best=self.has_best,
                                          has_themes=self.has_themes,
                                          get_drive_url=get_drive_url,
                                          unicode=unicode,
                                          enumerate=enumerate,
                                          set=set,
                                          list=list,
                                          reversed=reversed,
                                          sorted=sorted)
        self.env.jinja_env.filters['drive'] = get_drive_url
        self.env.jinja_env.add_extension('jinja2.ext.loopcontrols')
