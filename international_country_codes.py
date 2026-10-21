"""ISO-3166 identifiers for the ObraSignal international decision universe.

Kept local and dependency-free so the repository-state auditor is deterministic
in CI and production tooling.  European Union is the only non-country pseudo-
jurisdiction and deliberately uses EU/EU.
"""

_COUNTRY_CODES = """Austria|AT|AUT
Belgium|BE|BEL
Bulgaria|BG|BGR
Brazil|BR|BRA
Canada|CA|CAN
Switzerland|CH|CHE
Chile|CL|CHL
Colombia|CO|COL
Cyprus|CY|CYP
Czech Republic|CZ|CZE
Germany|DE|DEU
Denmark|DK|DNK
Dominican Republic|DO|DOM
Ecuador|EC|ECU
Spain|ES|ESP
Estonia|EE|EST
European Union|EU|EU
Finland|FI|FIN
France|FR|FRA
United Kingdom|GB|GBR
Greece|GR|GRC
Guatemala|GT|GTM
Honduras|HN|HND
Croatia|HR|HRV
Hungary|HU|HUN
Ireland|IE|IRL
Iceland|IS|ISL
Italy|IT|ITA
South Korea|KR|KOR
Liechtenstein|LI|LIE
Lithuania|LT|LTU
Luxembourg|LU|LUX
Latvia|LV|LVA
Malta|MT|MLT
Netherlands|NL|NLD
Norway|NO|NOR
Peru|PE|PER
Poland|PL|POL
Portugal|PT|PRT
Paraguay|PY|PRY
Romania|RO|ROU
Slovakia|SK|SVK
Slovenia|SI|SVN
Sweden|SE|SWE
Algeria|DZ|DZA
Angola|AO|AGO
Antigua and Barbuda|AG|ATG
Argentina|AR|ARG
Australia|AU|AUS
Bahamas|BS|BHS
Barbados|BB|BRB
Belize|BZ|BLZ
Benin|BJ|BEN
Bolivia|BO|BOL
Botswana|BW|BWA
Burkina Faso|BF|BFA
Burundi|BI|BDI
Cabo Verde|CV|CPV
Cameroon|CM|CMR
Central African Republic|CF|CAF
Chad|TD|TCD
Comoros|KM|COM
Costa Rica|CR|CRI
Cuba|CU|CUB
Côte d’Ivoire|CI|CIV
DRC|CD|COD
Djibouti|DJ|DJI
Dominica|DM|DMA
Egypt|EG|EGY
El Salvador|SV|SLV
Equatorial Guinea|GQ|GNQ
Eritrea|ER|ERI
Eswatini|SZ|SWZ
Ethiopia|ET|ETH
Faroe Islands|FO|FRO
Gabon|GA|GAB
Gambia|GM|GMB
Ghana|GH|GHA
Greenland|GL|GRL
Grenada|GD|GRD
Guinea|GN|GIN
Guinea-Bissau|GW|GNB
Guyana|GY|GUY
Haiti|HT|HTI
India|IN|IND
Indonesia|ID|IDN
Jamaica|JM|JAM
Japan|JP|JPN
Kenya|KE|KEN
Lesotho|LS|LSO
Liberia|LR|LBR
Libya|LY|LBY
Madagascar|MG|MDG
Malawi|MW|MWI
Mali|ML|MLI
Mauritania|MR|MRT
Mauritius|MU|MUS
Mexico|MX|MEX
Morocco|MA|MAR
Mozambique|MZ|MOZ
Namibia|NA|NAM
New Zealand|NZ|NZL
Nicaragua|NI|NIC
Niger|NE|NER
Nigeria|NG|NGA
Panama|PA|PAN
Philippines|PH|PHL
Republic of Congo|CG|COG
Rwanda|RW|RWA
Saint Kitts and Nevis|KN|KNA
Saint Lucia|LC|LCA
Saint Vincent and the Grenadines|VC|VCT
Saudi Arabia|SA|SAU
Senegal|SN|SEN
Seychelles|SC|SYC
Sierra Leone|SL|SLE
Singapore|SG|SGP
Somalia|SO|SOM
South Sudan|SS|SSD
Sudan|SD|SDN
Suriname|SR|SUR
São Tomé and Príncipe|ST|STP
Taiwan|TW|TWN
Tanzania|TZ|TZA
Togo|TG|TGO
Trinidad and Tobago|TT|TTO
Tunisia|TN|TUN
Uganda|UG|UGA
Ukraine|UA|UKR
United Arab Emirates|AE|ARE
Venezuela|VE|VEN
Zambia|ZM|ZMB
Zimbabwe|ZW|ZWE
Uruguay|UY|URY
United States|US|USA
South Africa|ZA|ZAF"""

COUNTRY_INDEX = {
    name: (iso2, iso3)
    for name, iso2, iso3 in (
        line.split("|", 2) for line in _COUNTRY_CODES.splitlines() if line.strip()
    )
}

COUNTRY_ALIASES = {
    "EU": "European Union",
    "UK": "United Kingdom",
    "Great Britain": "United Kingdom",
    "United States of America": "United States",
    "USA": "United States",
    "Czechia": "Czech Republic",
    "Korea": "South Korea",
    "KOR": "South Korea",
}

ISO3_TO_COUNTRY = {iso3: country for country, (_, iso3) in COUNTRY_INDEX.items()}
