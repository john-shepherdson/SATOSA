"""
Contains help methods and classes to perform tests.
"""
import base64
import tempfile
from datetime import datetime
from urllib.parse import parse_qsl, urlparse

from bs4 import BeautifulSoup

from satosa.backends.base import BackendModule
from satosa.frontends.base import FrontendModule
from satosa.internal import AuthenticationInformation
from satosa.internal import InternalData
from satosa.micro_services.base import RequestMicroService, ResponseMicroService
from satosa.response import Response



def generate_cert():
    cert_info = {
        "cn": "localhost",
        "country_code": "se",
        "state": "ac",
        "city": "Umea",
        "organization": "ITS",
        "organization_unit": "DIRG"
    }
    osw = OpenSSLWrapper()
    cert_str, key_str = osw.create_certificate(cert_info, request=False)
    return cert_str, key_str


def write_cert(cert_path, key_path):
    cert, key = generate_cert()
    with open(cert_path, "wb") as cert_file:
        cert_file.write(cert)
    with open(key_path, "wb") as key_file:
        key_file.write(key)


class FileGenerator(object):
    """
    Creates different types of temporary files that is useful for testing.
    """
    _instance = None

    def __init__(self):
        if FileGenerator._instance:
            raise TypeError('Singletons must be accessed through `get_instance()`.')
        else:
            FileGenerator._instance = self
        self.generate_certs = {}
        self.metadata = {}

    @staticmethod
    def get_instance():
        """
        :rtype: FileGenerator

        :return: A singleton instance of the class.
        """
        if FileGenerator._instance is None:
            FileGenerator._instance = FileGenerator()
        return FileGenerator._instance

    def generate_cert(self, code=None):
        """
        Will generate a certificate and key. If code is used the same certificate and key will
        always be returned for the same code.
        :type code: str
        :rtype: (tempfile._TemporaryFileWrapper, tempfile._TemporaryFileWrapper)

        :param: code: A unique code to represent a certificate and key.
        :return: A certificate and key temporary file.
        """
        if code in self.generate_certs:
            return self.generate_certs[code]

        cert_str, key_str = generate_cert()

        cert_file = tempfile.NamedTemporaryFile()
        cert_file.write(cert_str)
        cert_file.flush()
        key_file = tempfile.NamedTemporaryFile()
        key_file.write(key_str)
        key_file.flush()
        if code is not None:
            self.generate_certs[code] = cert_file, key_file
        return cert_file, key_file

    def create_metadata(self, config, code=None):
        """
        Will generate a metadata file. If code is used the same metadata file will
        always be returned for the same code.
        :type config: {dict}
        :type code: str

        :param config: A SAML configuration.
        :param code: A unique code to represent a certificate and key.
        """
        if code in self.metadata:
            return self.metadata[code]

        desc = create_metadata_from_config_dict(config)

        tmp_file = tempfile.NamedTemporaryFile()
        tmp_file.write(desc.encode("utf-8"))
        tmp_file.flush()
        if code:
            self.metadata[code] = tmp_file
        return tmp_file


def private_to_public_key(pk_file):
    f = open(pk_file, 'r')
    pk = RSA.importKey(f.read())
    return pk.publickey().exportKey('PEM')


def create_name_id():
    """
    :rtype: str

    :return: Returns a SAML nameid as XML string.
    """
    test_name_id = """<?xml version="1.0" encoding="utf-8"?>
<NameID xmlns="urn:oasis:names:tc:SAML:2.0:assertion"
  Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
  SPProvidedID="sp provided id">
  tmatsuo@example.com
</NameID>
"""
    return name_id_from_string(test_name_id)


def create_name_id_policy_transient():
    """
    Creates a transient name id policy.
    :return:
    """
    nameid_format = NAMEID_FORMAT_TRANSIENT
    name_id_policy = NameIDPolicy(format=nameid_format)
    return name_id_policy


def create_name_id_policy_persistent():
    """
    Creates a transient name id policy.
    :return:
    """
    nameid_format = NAMEID_FORMAT_PERSISTENT
    name_id_policy = NameIDPolicy(format=nameid_format)
    return name_id_policy


class FakeBackend(BackendModule):
    def __init__(self, start_auth_func=None, internal_attributes=None,
                 base_url="", name="FakeBackend",
                 register_endpoints_func=None):
        super().__init__(None, internal_attributes, base_url, name)

        self.start_auth_func = start_auth_func
        self.register_endpoints_func = register_endpoints_func

    def start_auth(self, context, request_info, state):
        """
        TODO comment
        :type context: TODO comment
        :type request_info: TODO comment
        :type state: TODO comment

        :param context: TODO comment
        :param request_info: TODO comment
        :param state: TODO comment
        """
        if self.start_auth:
            return self.start_auth(context, request_info, state)
        return None

    def register_endpoints(self):
        """
        TODO comment
        """
        if self.register_endpoints_func:
            return self.register_endpoints_func()
        return None


class FakeFrontend(FrontendModule):
    """
    TODO comment
    """

    def __init__(self, handle_authn_request_func=None, internal_attributes=None,
                 base_url="", name="FakeFrontend",
                 handle_authn_response_func=None,
                 register_endpoints_func=None):
        super().__init__(None, internal_attributes, base_url, name)
        self.handle_authn_request_func = handle_authn_request_func
        self.handle_authn_response_func = handle_authn_response_func
        self.register_endpoints_func = register_endpoints_func

    def handle_authn_request(self, context, binding_in):
        """
        TODO comment

        :type context:
        :type binding_in:

        :param context:
        :param binding_in:
        :return:
        """
        if self.handle_authn_request_func:
            return self.handle_authn_request_func(context, binding_in)
        return None

    def handle_authn_response(self, context, internal_response, state):
        """
        TODO comment
        :type context: TODO comment
        :type internal_response: TODO comment
        :type state: TODO comment

        :param context: TODO  comment
        :param internal_response: TODO comment
        :param state: TODO comment
        :return: TODO comment
        """
        if self.handle_authn_response_func:
            return self.handle_authn_response_func(context, internal_response, state)
        return None

    def register_endpoints(self, backend_names):
        if self.register_endpoints_func:
            return self.register_endpoints_func(backend_names)


class TestBackend(BackendModule):
    __test__ = False

    def __init__(self, auth_callback_func, internal_attributes, config, base_url, name):
        super().__init__(auth_callback_func, internal_attributes, base_url, name)

    def register_endpoints(self):
        return [("^{}/response$".format(self.name), self.handle_response)]

    def start_auth(self, context, internal_request):
        return Response("Auth request received, passed to test backend")

    def handle_response(self, context):
        auth_info = AuthenticationInformation("test", str(datetime.now()), "test_issuer")
        internal_resp = InternalData(auth_info=auth_info)
        internal_resp.attributes = context.request
        internal_resp.subject_id = "test_user"
        return self.auth_callback_func(context, internal_resp)


class TestFrontend(FrontendModule):
    __test__ = False

    def __init__(self, auth_req_callback_func, internal_attributes, config, base_url, name):
        super().__init__(auth_req_callback_func, internal_attributes, base_url, name)

    def register_endpoints(self, backend_names):
        url_map = [("^{}/{}/request$".format(p, self.name), self.handle_request) for p in backend_names]
        return url_map

    def handle_request(self, context):
        internal_req = InternalData(
            subject_type=NAMEID_FORMAT_TRANSIENT, requester="test_client"
        )
        return self.auth_req_callback_func(context, internal_req)

    def handle_authn_response(self, context, internal_resp):
        return Response("Auth response received, passed to test frontend")


class TestRequestMicroservice(RequestMicroService):
    __test__ = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def register_endpoints(self):
        return [("^request_microservice/callback$", self.callback)]

    def callback(self):
        pass


class TestResponseMicroservice(ResponseMicroService):
    __test__ = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def register_endpoints(self):
        return [("^response_microservice/callback$", self.callback)]

    def callback(self):
        pass
