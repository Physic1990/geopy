#from geopy.geocoders import Nominatim

# Initialize the Nominatim geocoder with a proper user agent
#geolocator = Nominatim(user_agent="my_unique_geocoding_app_v1.0")


# Geocode the address
#location = geolocator.geocode("380 New York St, Redlands")

# Print the address
#print(location.address)

from geopy.geocoders import ArcGIS

# Unauthenticated mode
#geolocator = ArcGIS()

# Geocode an address (get latitude and longitude from address)
location = geolocator.geocode("1600 Amphitheatre Parkway, Mountain View, CA")
print("Address:", location.address)
print("Latitude:", location.latitude)
print("Longitude:", location.longitude)

# Reverse geocode (get address from latitude and longitude)
reverse_location = geolocator.reverse((location.latitude, location.longitude))
print("Reverse Address:", reverse_location.address)
print("_____________________")

# Authenticated mode
username = 'sniraula_arcgis_devlabs'
password = 'CopaAmericaHouston@13949'
referer = 'http://www.example.com'

geolocator_auth = ArcGIS(username=username, password=password, referer=referer)

# Geocode an address with authentication
location_auth = geolocator_auth.geocode("1600 Amphitheatre Parkway, Mountain View, CA")
print("Authenticated Address:", location_auth.address)
print("Authenticated Latitude:", location_auth.latitude)
print("Authenticated Longitude:", location_auth.longitude)

# Reverse geocode with authentication
reverse_location_auth = geolocator_auth.reverse((location_auth.latitude, location_auth.longitude))
print("Authenticated Reverse Address:", reverse_location_auth.address)

