from flask import Blueprint
from flask_restful import reqparse, Resource, Api

from coalaip import CoalaIp, ModelDataError, entities
from coalaip_bigchaindb.plugin import Plugin
from web.models import right_model, public_user_model, user_model
from web.utils import get_bigchaindb_api_url


coalaip = CoalaIp(Plugin(get_bigchaindb_api_url()))

right_views = Blueprint('right_views', __name__)
right_api = Api(right_views)


def load_right(entity_id):
    # We can't be sure of the type of Right that's given by using just the
    # id, so let's assume it's a normal Right first before trying to make a
    # Copyright
    try:
        right = entities.Right.from_persist_id(entity_id,
                                               plugin=coalaip.plugin,
                                               force_load=True)
    except ModelDataError:
        right = entities.Copyright.from_persist_id(entity_id,
                                                   plugin=coalaip.plugin,
                                                   force_load=True)
    return right


class RightApi(Resource):
    def get(self, entity_id):
        right = load_right(entity_id)
        return right.to_jsonld()


class RightListApi(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('right', type=right_model, required=True,
                            location='json')
        parser.add_argument('sourceRightId', type=str, required=True,
                            location='json')
        parser.add_argument('currentHolder', type=user_model, required=True,
                            location='json')
        args = parser.parse_args()

        source_right_id = args['sourceRightId']
        right = args['right']
        right['source'] = source_right_id

        current_holder = args['currentHolder']
        current_holder['public_key'] = current_holder.pop('publicKey')
        current_holder['private_key'] = current_holder.pop('privateKey')

        right = coalaip.derive_right(right_data=right,
                                     current_holder=current_holder)

        right_jsonld = right.to_jsonld()
        right_jsonld['@id'] = right.persist_id
        res = {'right': right_jsonld}

        return res


class RightHistoryApi(Resource):
    def get(self, right_id):
        # Don't worry about whether the entity corresponding to `right_id` is a
        # Right or a Copyright since we won't be loading it
        right = entities.Right.from_persist_id(right_id, plugin=coalaip.plugin,
                                               force_load=False)
        return [{
            'user': {
                'publicKey': event['user']['public_key'],
                'privateKey': event['user']['private_key'],
            },
            'eventId': event['event_id'],
        } for event in right.history]


class RightTransferApi(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('rightId', type=str, required=True,
                            location='json')
        parser.add_argument('currentHolder', type=user_model, required=True,
                            location='json')
        parser.add_argument('to', type=public_user_model, required=True,
                            location='json')
        parser.add_argument('rightsAssignment', type=dict, location='json')
        args = parser.parse_args()

        right_id = args['rightId']
        current_holder = args['currentHolder']
        to = args['to']
        rights_assignment = args['rightsAssignment']

        for user in [current_holder, to]:
            user['public_key'] = user.pop('publicKey')
            user['private_key'] = user.pop('privateKey')

        right = load_right(right_id)
        res = coalaip.transfer_right(right=right,
                                     rights_assignment_data=rights_assignment,
                                     current_holder=current_holder,
                                     to=to)

        res = {'rightsAssignment': res.to_jsonld()}

        return res


right_api.add_resource(RightApi, '/rights/<entity_id>', strict_slashes=False)
right_api.add_resource(RightHistoryApi, '/rights/history/<string:right_id>',
                       strict_slashes=False)
right_api.add_resource(RightListApi, '/rights', strict_slashes=False)
right_api.add_resource(RightTransferApi, '/rights/transfer',
                       strict_slashes=False)
