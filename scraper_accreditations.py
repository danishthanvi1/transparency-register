import logging
from datetime import datetime

import requests
from lxml import etree
# from pprint import pprint

from util import reg_representative, engine
from util import shortdateconv as dateconv

log = logging.getLogger('scraper_accreditations')

URL = "http://ec.europa.eu/transparencyregister/public/consultation/statistics.do?action=getLobbyistsXml&fileType=ACCREDITED_PERSONS"
_NS = "http://ec.europa.eu/transparencyregister/accreditedPerson/V1"
NS = '{%s}' % _NS


def parse(content):
    doc = etree.fromstring(content)
    for ap_el in doc.findall('.//' + NS + 'accreditedPerson'):
        ap = {
            'org_identification_code': ap_el.findtext(NS + 'orgIdentificationCode'),
            'number_of_ir': ap_el.findtext(NS + 'numberOfIR'),
            'xml': etree.tostring(ap_el),
            'org_name': ap_el.findtext(NS + 'orgName'),
            'title': ap_el.findtext(NS + 'title'),
            'first_name': ap_el.findtext(NS + 'firstName'),
            'last_name': ap_el.findtext(NS + 'lastName'),
            'start_date': dateconv(ap_el.findtext(NS + 'accreditationStartDate')),
            'end_date': dateconv(ap_el.findtext(NS + 'accreditationEndDate')),
            }
        yield ap


def save(tx, person, orgs):
    table = tx['reg_person']
    person['role'] = 'accredited'
    org_id = person['org_identification_code']
    name = '%s %s %s' % (person['title'] or '',
                         person['first_name'] or '',
                         person['last_name'] or '')
    name = name.strip()
    person['name'] = name
    person['first_seen'] = datetime.utcnow()
    person['last_seen'] = datetime.utcnow()
    existing = table.find_one(name=name, org_identification_code=org_id)
    if existing is not None:
        person['first_seen'] = existing['first_seen']
    log.debug("Accreditation: %s", name)
    if org_id not in orgs:
        recs = list(reg_representative.find(identification_code=org_id))
        if len(recs):
            orgs[org_id] = max(recs, key=lambda o: o['last_update_date'])
        else:
            log.warn("Cannot associate with a registered interest: %r",
                     person['org_name'])
            orgs[org_id] = None

    if orgs[org_id]:
        person['representative_etl_id'] = orgs[org_id]['etl_id']

    table.upsert(person, ['representative_etl_id', 'role', 'name'])


def extract_data(xml):
    orgs = {}
    log.info("Extracting accredditation data...")
    with engine as tx:
        for i, ap in enumerate(parse(xml)):
            save(tx, ap, orgs)
            if i % 100 == 0:
                log.info("Extracted: %s...", i)


def extract():
    res = requests.get(URL)
    extract_data(res.content)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    extract()

