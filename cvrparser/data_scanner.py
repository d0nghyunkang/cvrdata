from sqlalchemy import select, tuple_
from . import parser_company as virksomhed_parser
from . import parser_person as person_parser
from . import parser_punit as penhed_parser
from . import field_parser as field_parser
from . import adresse
from . import alchemy_tables
from . import Session


def insert_values(dicts, parser):
    """ Parse Cvr Values from cvr dictionaries

    Args:
    -----
    @param dicts: list, lists of cvr data dicts
    @param parser: parser, that extracts the data
    """

    for j, d in enumerate(dicts):
        parser.insert(d)
        if ((j+1) % 1000) == 0:
            print('{0} objects parsed'.format(j))
    parser.commit()


def get_company_data_parsers(key_store):
    """ Get all parsers for parsing the information fields in company data """
    factory = virksomhed_parser.VirksomhedParserFactory(key_store)
    virk_value = factory.get_value_parser()
    return virk_value


def get_person_data_parsers(key_store):
    """ Get all parsers for parsing the information fields in person data

    :param key_store: Mapping
    """
    factory = person_parser.PersonParserFactory(key_store=key_store)
    person_value = factory.get_value_parser()
    return person_value


def get_penhed_data_parsers(key_store):
    factory = penhed_parser.PenhedParserFactory(key_store=key_store)
    penhed_value = factory.get_value_parser()
    return penhed_value


def get_company_dynamic_parsers(key_store):
    return virksomhed_parser.VirksomhedParserFactory(key_store=key_store).get_dyna_parser()


def get_person_dynamic_parsers(key_store):
    return person_parser.PersonParserFactory(key_store=key_store).get_dyna_parser()


def get_penhed_dynamic_parsers(key_store):
    return penhed_parser.PenhedParserFactory(key_store=key_store).get_dyna_parser()


def get_company_static_parser(key_store=None):
    return virksomhed_parser.VirksomhedParserFactory(key_store=key_store).get_static_parser()


def get_person_static_parser(key_store=None):
    return person_parser.PersonParserFactory(key_store=key_store).get_static_parser()


def get_penhed_static_parser(key_store=None):
    return penhed_parser.PenhedParserFactory(key_store=key_store).get_static_parser()


class Mapping(object):
    """ Simple mapping object that maps values to database ids that caches updates"""
    def __init__(self, keycol, val, keylen=1):
        self.mapped = {}
        self.unmapped = set()
        self.val = val
        self.keycol = keycol
        self.keylen = keylen

    def update(self):
        """ Update the keys of all the unmapped values if possible
        sessionnize this

        :returns
            missing, set of elements still not mapped
        """
        missing = set()
        if len(self.unmapped) > 0:
            session = Session()
            if self.keylen == 1:
                query = session.query(self.keycol, self.val).filter(self.keycol.in_(self.unmapped))
            else:
                query = session.query(*self.keycol, self.val).filter(tuple_(*self.keycol).in_(self.unmapped))
            qres = query.all()
            res = [x for x in qres]
            if self.keylen == 1:
                new = {x[0]: x[-1] for x in res}
            else:
                # new = {x[:self.keylen]: x[self.keylen:] for x in res}
                new = {x[:self.keylen]: x[-1] for x in res}
            new_keys = set(new.keys())
            assert new_keys.issubset(self.unmapped)
            missing = self.unmapped - set(new.keys())
            self.mapped.update(new)
            self.unmapped = missing
        return missing

    def __getitem__(self, key):
        return self.mapped[key]

    def __contains__(self, key):
        return key in self.mapped or key in self.unmapped

    def add(self, obj):
        self.unmapped.add(obj)


class KeyStore(object):

    def __init__(self):
        self.name_mapping = Mapping(val=alchemy_tables.Navne.navnid,
                                    keycol=alchemy_tables.Navne.navn)
        self.kontakt_mapping = Mapping(val=alchemy_tables.Kontaktinfo.oplysningid,
                                       keycol=alchemy_tables.Kontaktinfo.kontaktoplysning)
        self.regnummer_mapping = Mapping(val=alchemy_tables.Regnummer.regid,
                                         keycol=alchemy_tables.Regnummer.regnummer)
        self.virksomhedsstatus_mapping = Mapping(val=alchemy_tables.Virksomhedsstatus.virksomhedsstatusid,
                                                 keycol=alchemy_tables.Virksomhedsstatus.virksomhedsstatus)
        self.status_mapping = Mapping(val=alchemy_tables.Statuskode.statusid,
                                      keylen=2,
                                      keycol=(alchemy_tables.Statuskode.statuskode,
                                              alchemy_tables.Statuskode.kreditoplysningskode))
        self.branche_mapping = Mapping(val=alchemy_tables.Branche.branchekode,
                                       keycol=alchemy_tables.Branche.branchekode)
        self.virksomhedsform_mapping = Mapping(val=alchemy_tables.Virksomhedsform.virksomhedsformkode,
                                               keycol=alchemy_tables.Virksomhedsform.virksomhedsformkode)

    def get_virksomhedsform_mapping(self):
        self.virksomhedsform_mapping.update()
        return self.virksomhedsform_mapping

    def get_branche_mapping(self):
        self.branche_mapping.update()
        return self.branche_mapping

    def get_name_mapping(self):
        self.name_mapping.update()
        return self.name_mapping

    def get_kontakt_mapping(self):
        self.kontakt_mapping.update()
        return self.kontakt_mapping

    def get_regnummer_mapping(self):
        self.regnummer_mapping.update()
        return self.regnummer_mapping

    def get_virksomhedsstatus_mapping(self):
        self.virksomhedsstatus_mapping.update()
        return self.virksomhedsstatus_mapping

    def get_status_mapping(self):
        self.status_mapping.update()
        return self.status_mapping


class DataParser(object):
    """ Wrapper class for data parsers to store cache between uses"""
    def __init__(self, _type):
        """

        :param _type: str, cvr object type
        """
        self.keystore = KeyStore()
        self._type = _type
        if _type == 'Vrvirksomhed':
            self.data_parser = get_company_data_parsers
            self.dynamic_parser = get_company_dynamic_parsers
            self.static_parser = get_company_static_parser
        elif _type == 'Vrdeltagerperson':
            self.data_parser = get_person_data_parsers
            self.dynamic_parser = get_person_dynamic_parsers
            self.static_parser = get_person_static_parser
        elif _type == 'VrproduktionsEnhed':
            self.data_parser = get_penhed_data_parsers
            self.dynamic_parser = get_penhed_dynamic_parsers
            self.static_parser = get_penhed_static_parser
        else:
            raise Exception('Bad Type {0}'.format(_type))

    def parse_data(self, dicts):
        insert_values(dicts, self.data_parser(self.keystore))

    def parse_dynamic_data(self, dicts):
        insert_values(dicts, self.dynamic_parser(self.keystore))

    def parse_static_data(self, dicts):
        insert_values(dicts, self.static_parser(self.keystore))


class AddressParserFactory(object):
    """ Simple Factory for making an adresse parser
    TODO: change to just add poststring if no dawa available
    """
    def __init__(self):
        self.address_tables = None
        self.dawa_translater = None

    def create_parser(self, use_matcher=False):
        if use_matcher:
            return AddressParser(alchemy_tables.Adresseupdate, self.get_dawa_translater())
        else:
            return AddressParser(alchemy_tables.Adresseupdate, None)

    def get_address_tables(self):
        if self.address_tables is None:
            print('Make address tables once and for all all: takes a while - better update a lot :)')
            self.address_tables = adresse.get_adresse_maps()
        return self.address_tables

    def get_dawa_translater(self):
        if self.dawa_translater is None:
            self.dawa_translater = adresse.AdressTranslater({}, **self.get_address_tables())
        return self.dawa_translater


class AddressParser(object):
    def __init__(self,  tables_class, dawa_translater):
        self.adresse_parser = field_parser.AddressParser(tables_class, dawa_translater)

    def parse_address_data(self, dicts):
        insert_values(dicts, self.adresse_parser)
