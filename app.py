from flask import Flask, request
from pymongo import MongoClient

from bs4 import BeautifulSoup
from datetime import date
import requests as rq
import json
import lxml

application = Flask(__name__)

cluster = MongoClient('environ.get('MONGO_PW')')
db = cluster['ReportStat']
collection = db['reports']

subdomen = "podruzhki"

url_amo_create_contacts = f"https://{subdomen}.amocrm.ru/api/v4/contacts"
url_amo_create_leads = f"https://{subdomen}.amocrm.ru/api/v4/leads"

pipeline_id = 3662985


def ph_fix(input_ph: str) -> str:
    if len(input_ph) == 12 and input_ph.startswith('+') and input_ph[1:].isdigit():
        return input_ph
    else:
        output_ph = ['+']
        [output_ph.append(i) for i in input_ph.strip() if i.isdigit()]
        output_ph[1] = '7' if output_ph[1] == '8' else '7'
        return ''.join(output_ph)


with open('access_token.txt', 'r') as file:
    amo_token = file.read()


def amo_worker(data):
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
    params_amo_post_lead = [
        {
            "name": deal['form_name'],
            "pipeline_id": pipeline_id,
            "custom_fields_values": [
                {
                    "field_id": 621325,
                    "values": [
                        {
                            "value": deal['city'],
                            "enum_code": "city",
                        }
                    ]
                },
                {
                    "field_id": 528795,
                    "values": [
                        {
                            "value": deal['phone']
                        }
                    ]
                },
                {
                    "field_id": 528793,
                    "values": [
                        {
                            "value": deal['name']
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

    add_leads = rq.post(url_amo_create_leads,
                        data=json.dumps(params_amo_post_lead),
                        headers={'Authorization': f'Bearer {amo_token}'})
    add_leads_response = add_leads.json()
    print(add_leads_response)

    get_contacts = rq.get(f"https://{subdomen}.amocrm.ru/private/api/contact_search.php?SEARCH={ph_fix(deal['phone'])}",
                          headers={'Authorization': f'Bearer {amo_token}'})

    soup = BeautifulSoup(get_contacts.content, 'lxml')
    print(soup.contacts.contact.id.text)

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
                              headers={'Authorization': f'Bearer {amo_token}'})
        print(add_contact.json())

    finally:
        """ ПРОВЕРКА НА СУЩЕСТВОВАНИЕ """
        get_contacts2 = rq.get(
            f"https://{subdomen}.amocrm.ru/private/api/contact_search.php?SEARCH={ph_fix(deal['phone'])}",
            headers={'Authorization': f'Bearer {amo_token}'})
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
                             headers={'Authorization': f'Bearer {amo_token}'})
        print(add_entity.json())


@application.route('/')
def hello_world():
    return 'Hello World!'


@application.route('/addleads', methods=['POST'])
def processing():
    data = json.loads(request.data)
    print(data)
    if data['type'] == 'confirmation':
        return "95ec0a72"
    elif data['type'] == 'lead_forms_new':
        amo_worker(data)
        return 'ok'


if __name__ == '__main__':
    application.run()
