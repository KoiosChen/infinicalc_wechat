from flask_restplus import fields, reqparse

head_parser = reqparse.RequestParser()
head_parser.add_argument('Authorization', required=True, location='headers')

return_dict = {'code': fields.String(required=True, description='success | false'),
               'data': fields.Raw(description='string or json'),
               'message': fields.String(description='成功或者失败的文字信息')}
