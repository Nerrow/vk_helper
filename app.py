from flask import Flask, request, make_response
from pymongo import MongoClient

from bs4 import BeautifulSoup
from datetime import date
from celery import Celery
import requests as rq
import json
import lxml

application = Flask(__name__)

cluster = MongoClient('mongo.pw')
db = cluster['ReportStat']
collection = db['podruge_normalized2']

subdomen = "podruzhki"

url_amo_create_contacts = f"https://{subdomen}.amocrm.ru/api/v4/contacts"
url_amo_create_leads = f"https://{subdomen}.amocrm.ru/api/v4/leads"

pipeline_id = 3662985

celery = Celery(application.name, broker='redis://localhost:6379/0')
celery.conf.update(application.config)


def ph_fix(input_ph: str) -> str:
    if len(input_ph) == 12 and input_ph.startswith('+') and input_ph[1:].isdigit():
        return input_ph
    else:
        output_ph = ['+']
        [output_ph.append(i) for i in input_ph.strip() if i.isdigit()]
        output_ph[1] = '7' if output_ph[1] == '8' else '7'
        return ''.join(output_ph)


@celery.task
def amo_worker(data):
    with open('access_token.txt', 'r') as file:
        amo_token = file.read()
    
    headers = {'Authorization': f'Bearer {amo_token}'}
    
        if data['object']['form_name'] == '':  # CHANGE
        deal = {
            "form_name": data['object']['form_name'],
            "user_id": data['object']['user_id'],
            "name": data['object']['answers'][0]['answer'],
            "phone": data['object']['answers'][1]['answer'],
            "city": data['object']['answers'][2]['answer'],
            "alreadyBeen": data['object']['answers'][3]['answer'],
            "sale": data['object']['answers'][6]['answer'],
            "date": str(date.today()),
        }

        add_to_db = db.reports.insert_one(deal).inserted_id
        print(add_to_db)

        """ ДОБАВЛЕНИЕ СДЕЛКИ """
        print(deal['alreadyBeen'])
        params_amo_post_lead = [
            {
                "name": deal['form_name'],
                "pipeline_id": pipeline_id,
                "custom_fields_values": [
                    {
                        "field_id": 692252,
                        "values": [
                            {
                                "value": deal['alreadyBeen'],
                            }
                        ]
                    },
                    {
                        "field_id": 688701,
                        "values": [
                            {
                                "value": deal['sale'],
                            }
                        ]
                    }
                ],
                "_embedded": {
                    "tags": [
                        {
                            "name": "вк"
                        }
                    ]
                }
            }]
    else:
        deal = {
            "form_name": data['object']['form_name'],
            "user_id": data['object']['user_id'],
            "name": data['object']['answers'][0]['answer'],
            "phone": data['object']['answers'][1]['answer'],
            "city": data['object']['answers'][2]['answer'],
            "alreadyBeen": data['object']['answers'][3]['answer'],
            "date": str(date.today())
        }

        add_to_db = db.reports.insert_one(deal).inserted_id
        print(add_to_db)

        """ ДОБАВЛЕНИЕ СДЕЛКИ """
        print(deal['alreadyBeen'])
        params_amo_post_lead = [
            {
                "name": deal['form_name'],
                "pipeline_id": pipeline_id,
                "custom_fields_values": [{
                    "field_id": 692252,
                    "values": [
                        {
                            "value": deal['alreadyBeen'],
                        }
                    ]
                }],
                "_embedded": {
                    "tags": [
                        {
                            "name": "вк"
                        }
                    ]
                }
            }]

    add_leads = rq.post(url_amo_create_leads,
                        data=json.dumps(params_amo_post_lead),
                        headers=headers)
    add_leads_response = add_leads.json()

    get_contacts = rq.get(f"https://{subdomen}.amocrm.ru/private/api/contact_search.php?SEARCH={ph_fix(deal['phone'])}",
                          headers=headers)

    soup = BeautifulSoup(get_contacts.content, 'lxml')

    try:
        if soup.find('contacts/contact/id').text != 0:
            print(soup.find('contacts/contact/id').text)

    except AttributeError:

        params_amo_post_contact = [{
            "first_name": deal['name'],
            "custom_fields_values": [
                {
                    "field_id": 528729,  # 913231
                    "values": [
                        {
                            "value": ph_fix(deal['phone']),
                            "enum_code": "MOB",
                        }
                    ]
                },
                {
                    "field_id": 621311,
                    "values": [
                        {
                            "value": deal['city'],
                            "enum_code": "city",
                        }
                    ]
                }
            ]
        }]

        """ ДОБАВЛЕНИЕ КОНТАКТА """
        add_contact = rq.post(url_amo_create_contacts,
                              data=json.dumps(params_amo_post_contact),
                              headers=headers)
        print(add_contact.json())

    finally:
        """ ПРОВЕРКА НА СУЩЕСТВОВАНИЕ """
        get_contacts2 = rq.get(
            f"https://{subdomen}.amocrm.ru/private/api/contact_search.php?SEARCH={ph_fix(deal['phone'])}",
            headers=headers)
        contact_id = BeautifulSoup(get_contacts2.content, 'lxml').contacts.contact.id.text
        print(contact_id)

        """ СВЯЗКА СУЩНОСТЕЙ """
        entity_id = add_leads_response['_embedded']['leads'][0]['id']
        print(entity_id)
        url_amo_add_entity = f"https://{subdomen}.amocrm.ru/api/v4/contacts/{contact_id}/link"

        params_amo_post_entity = [
            {
                "to_entity_id": entity_id,
                "to_entity_type": "leads",
            }
        ]

        add_entity = rq.post(url_amo_add_entity,
                             data=json.dumps(params_amo_post_entity),
                             headers=headers)
        print(add_entity.json())


@application.route('/')
def hello_world():
    return 'Hello World!'


@application.route('/addleads', methods=['POST'])
def processing():
    data = json.loads(request.data)
    print(data)
    if data['type'] == 'confirmation':
        return "afd8f2a4"
    elif data['type'] == 'lead_forms_new':
        make_response('ok')
        amo_worker.delay(data)
        return 'ok'


if __name__ == '__main__':
    application.run()
