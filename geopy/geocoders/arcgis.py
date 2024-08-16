import json
from functools import partial
from time import time
from urllib.parse import urlencode

from geopy.exc import (
    ConfigurationError,
    GeocoderAuthenticationFailure,
    GeocoderServiceError,
)
from geopy.geocoders.base import DEFAULT_SENTINEL, Geocoder, _synchronized
from geopy.location import Location
from geopy.util import logger

__all__ = ("ArcGIS", )

DEFAULT_WKID = 4326


class ArcGIS(Geocoder):
    """Geocoder using the ESRI ArcGIS API.

    Documentation at:
        https://developers.arcgis.com/rest/geocode/api-reference/overview-world-geocoding-service.htm
    """

    _TOKEN_EXPIRED = 498

    auth_path = '/sharing/generateToken'
    geocode_path = '/arcgis/rest/services/World/GeocodeServer/findAddressCandidates'
    reverse_path = '/arcgis/rest/services/World/GeocodeServer/reverseGeocode'

    def __init__(
            self,
            username=None,
            password=None,
            token=None,
            *,
            referer=None,
            token_lifetime=60,
            scheme=None,
            timeout=DEFAULT_SENTINEL,
            proxies=DEFAULT_SENTINEL,
            user_agent=None,
            ssl_context=DEFAULT_SENTINEL,
            adapter_factory=None,
            auth_domain='www.arcgis.com',
            domain='geocode.arcgis.com'
    ):
        """

        :param str username: ArcGIS username. Required if authenticated
            mode is desired.

        :param str password: ArcGIS password. Required if authenticated
            mode is desired.

        :param str token: ArcGIS API for Python token. If provided, used
            for authentication instead of username/password.

        :param str referer: Required if authenticated mode is desired.
            `Referer` HTTP header to send with each request,
            e.g., ``'http://www.example.com'``. This is tied to an issued token,
            so fielding queries for multiple referrers should be handled by
            having multiple ArcGIS geocoder instances.

        :param int token_lifetime: Desired lifetime, in minutes, of an
            ArcGIS-issued token.

        :param str scheme:
            See :attr:`geopy.geocoders.options.default_scheme`.
            If authenticated mode is in use, it must be ``'https'``.

        :param int timeout:
            See :attr:`geopy.geocoders.options.default_timeout`.

        :param dict proxies:
            See :attr:`geopy.geocoders.options.default_proxies`.

        :param str user_agent:
            See :attr:`geopy.geocoders.options.default_user_agent`.

        :type ssl_context: :class:`ssl.SSLContext`
        :param ssl_context:
            See :attr:`geopy.geocoders.options.default_ssl_context`.

        :param callable adapter_factory:
            See :attr:`geopy.geocoders.options.default_adapter_factory`.

            .. versionadded:: 2.0

        :param str auth_domain: Domain where the target ArcGIS auth service
            is hosted. Used only in authenticated mode (i.e. username,
            password and referer are set).

        :param str domain: Domain where the target ArcGIS service
            is hosted.
        """
        super().__init__(
            scheme=scheme,
            timeout=timeout,
            proxies=proxies,
            user_agent=user_agent,
            ssl_context=ssl_context,
            adapter_factory=adapter_factory,
        )
        if (username or password or referer) and not (username and password and referer):
            raise ConfigurationError(
                "Authenticated mode requires username, password, and referer"
            )
        if token and self.scheme != 'https':
            raise ConfigurationError(
                "Authenticated mode with token requires scheme of 'https'"
            )

        self.username = username
        self.password = password
        self.token = token
        self.referer = referer
        self.auth_domain = auth_domain.strip('/')
        self.auth_api = (
            '%s://%s%s' % (self.scheme, self.auth_domain, self.auth_path)
        )

        self.token_lifetime = token_lifetime * 60  # store in seconds

        self.domain = domain.strip('/')
        self.api = (
            '%s://%s%s' % (self.scheme, self.domain, self.geocode_path)
        )
        self.reverse_api = (
            '%s://%s%s' % (self.scheme, self.domain, self.reverse_path)
        )

        # Mutable state
        self.token_expiry = None

    def geocode(self, query, *, exactly_one=True, timeout=DEFAULT_SENTINEL,
                out_fields=None):
        """
        Return a location point by address.

        :param str query: The address or query you wish to geocode.

        :param bool exactly_one: Return one result or a list of results, if
            available.

        :param int timeout: Time, in seconds, to wait for the geocoding service
            to respond before raising a :class:`geopy.exc.GeocoderTimedOut`
            exception. Set this only if you wish to override, on this call
            only, the value set during the geocoder's initialization.

        :param out_fields: A list of output fields to be returned in the
            attributes field of the raw data. This can be either a python
            list/tuple of fields or a comma-separated string. See
            https://developers.arcgis.com/rest/geocode/api-reference/geocoding-service-output.htm
            for a list of supported output fields. If you want to return all
            supported output fields, set ``out_fields="*"``.
        :type out_fields: str or iterable

        :rtype: ``None``, :class:`geopy.location.Location` or a list of them, if
            ``exactly_one=False``.
        """
        params = {'singleLine': query, 'f': 'json'}
        if exactly_one:
            params['maxLocations'] = 1
        if out_fields is not None:
            if isinstance(out_fields, str):
                params['outFields'] = out_fields
            else:
                params['outFields'] = ",".join(out_fields)
        url = "?".join((self.api, urlencode(params)))
        logger.debug("%s.geocode: %s", self.__class__.__name__, url)
        callback = partial(self._parse_geocode, exactly_one=exactly_one)
        return self._authenticated_call_geocoder(url, callback, timeout=timeout)

    def _parse_geocode(self, response, exactly_one):
        if 'error' in response:
            raise GeocoderServiceError(str(response['error']))

        # Success; convert from the ArcGIS JSON format.
        if not len(response['candidates']):
            return None
        geocoded = []
        for resource in response['candidates']:
            geometry = resource['location']
            geocoded.append(
                Location(
                    resource['address'], (geometry['y'], geometry['x']), resource
                )
            )
        if exactly_one:
            return geocoded[0]
        return geocoded

    def reverse(self, query, *, exactly_one=True, timeout=DEFAULT_SENTINEL,
                distance=None):
        """
        Return an address by location point.

        :param query: The coordinates for which you wish to obtain the
            closest human-readable addresses.
        :type query: :class:`geopy.point.Point`, list or tuple of ``(latitude,
            longitude)``, or string as ``"%(latitude)s, %(longitude)s"``.

        :param bool exactly_one: Return one result or a list of results, if
            available.

        :param int timeout: Time, in seconds, to wait for the geocoding service
            to respond before raising a :class:`geopy.exc.GeocoderTimedOut`
            exception. Set this only if you wish to override, on this call
            only, the value set during the geocoder's initialization.

        :param int distance: Distance from the query location, in meters,
            within which to search. ArcGIS has a default of 100 meters, if not
            specified.

        :rtype: ``None``, :class:`geopy.location.Location` or a list of them, if
            ``exactly_one=False``.
        """
        location = self._coerce_point_to_string(query, "%(lon)s,%(lat)s")
        wkid = DEFAULT_WKID
        params = {'location': location, 'f': 'json', 'outSR': wkid}
        if distance is not None:
            params['distance'] = distance
        url = "?".join((self.reverse_api, urlencode(params)))
        logger.debug("%s.reverse: %s", self.__class__.__name__, url)
        callback = partial(self._parse_reverse, exactly_one=exactly_one)
        return self._authenticated_call_geocoder(url, callback, timeout=timeout)

    def _parse_reverse(self, response, exactly_one):
        if not len(response):
            return None
        if 'error' in response:
            # https://developers.arcgis.com/rest/geocode/api-reference/geocoding-service-output.htm
            if response['error']['code'] == 400:
                # 'details': ['Unable to find address for the specified location.']
                return None
            raise GeocoderServiceError(str(response['error']))
        address = response['address']
        location = (response['location']['y'], response['location']['x'])
        return Location(address['Match_addr'], location, address)

    def _authenticated_call_geocoder(self, url, callback, *, timeout):
        """
        Call the geocoder with a (potentially refreshed) ArcGIS token.
        """
        if self.token:
            # Use the provided token
            auth_params = {'token': self.token, 'referer': self.referer}
        else:
            if not self.token_expiry or time() >= self.token_expiry:
                # Get a new token if the current one is expired or missing
                self._refresh_authentication_token()
            auth_params = {'token': self.token, 'referer': self.referer}

        url = f"{url}&{urlencode(auth_params)}"
        return self._call_geocoder(url, callback, timeout=timeout)

    @_synchronized
    def _refresh_authentication_token(self):
        """
        Request an authentication token from ArcGIS.
        """
        assert self.username and self.password and self.referer

        if not self.token_expiry or time() >= self.token_expiry:
            # Get a new token
            logger.debug("%s: Refreshing token", self.__class__.__name__)
            response = self._call_geocoder(
                self.auth_api,
                self._parse_authentication_token,
                method='POST',
                headers={'Referer': self.referer},
                post_data={
                    'username': self.username,
                    'password': self.password,
                    'referer': self.referer,
                    'f': 'json',
                    'expiration': str(self.token_lifetime)
                }
            )
            return response
        return None

    def _parse_authentication_token(self, response):
        if 'error' in response:
            raise GeocoderAuthenticationFailure(
                str(response['error'])
            )
        self.token = response['token']
        self.token_expiry = time() + self.token_lifetime
        logger.debug(
            "%s: Refreshed token now expires at %s",
            self.__class__.__name__,
            self.token_expiry
        )
        return None
