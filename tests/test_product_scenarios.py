from datetime import datetime, timezone
from decimal import Decimal

from bangs.accommodation import AccommodationCandidate, AccommodationType, RateBasis, assess_accommodation
from bangs.comparator import ComparisonStatus, CostOption, compare_cost_options
from bangs.costs import CostBasis, CostLine, assess_cost_lines, combine_assessments
from bangs.equipment import EquipmentMode, EquipmentOption, RentalRateBasis, assess_equipment
from bangs.evidence import Availability, ConfirmationState, EvidenceBasis, RequirementBasis, SourceEvidence, TaxBasis, Visibility
from bangs.landed_cost import assess_landed_cost
from bangs.materials import MaterialPriceObservation, MaterialRequirement
from bangs.money import Money
from bangs.routes import DistanceBasis, FuelObservation, RouteDirection, RouteFacts, VehicleEconomics, assess_route_cost
from bangs.true_cost import JobCostCategory, JobCostContribution, assess_true_job_cost

NOW=datetime(2026,8,25,tzinfo=timezone.utc)
OBS=SourceEvidence("public observation", EvidenceBasis.MARKET_OBSERVATION, NOW)
QUOTE=SourceEvidence("supplier quote", EvidenceBasis.SUPPLIER_QUOTE, NOW)
ROUTE=SourceEvidence("route provider", EvidenceBasis.PROVIDER_FACT, NOW)

def test_product_1_daily_commute_vs_accommodation_for_10_workers_12_weeks():
    commute=assess_route_cost(RouteFacts(300,180,DistanceBasis.ROAD_PROVIDER,ROUTE), VehicleEconomics(10,FuelObservation(Money.of('1.8','EUR'),'PT',OBS)), direction=RouteDirection.ROUND_TRIP, number_of_trips=60, tolls_known=True)
    hotel=AccommodationCandidate('h','Crew hotel',AccommodationType.HOTEL,Money.of(70,'EUR'),RateBasis.ROOM_PER_NIGHT,2,OBS,ConfirmationState.AVAILABILITY_CONFIRMED)
    stay=assess_accommodation(hotel,crew_size=10,nights=84,now=NOW)
    result=compare_cost_options((CostOption('daily_commute',commute.assessment,Availability.AVAILABLE,ConfirmationState.AVAILABILITY_CONFIRMED,'crew_strategy'),CostOption('accommodation',stay.assessment,Availability.AVAILABLE,ConfirmationState.AVAILABILITY_CONFIRMED,'crew_strategy')))
    assert commute.assessment.known_total.amount == Decimal('6480.0')
    assert stay.assessment.known_total.amount == Decimal('29400')
    assert result.winner_id == 'daily_commute'

def test_product_2_cheaper_raw_supplier_can_lose_on_landed_cost():
    req=MaterialRequirement('x','Material X',Decimal('2000'),'m2',RequirementBasis.BOQ_EXPLICIT)
    pa=MaterialPriceObservation('a','x','A','m2',Money.of(8,'EUR'),TaxBasis.VAT_INCLUDED,OBS,Visibility.PUBLIC,availability=Availability.AVAILABLE)
    pb=MaterialPriceObservation('b','x','B','m2',Money.of('8.5','EUR'),TaxBasis.VAT_INCLUDED,OBS,Visibility.PUBLIC,availability=Availability.AVAILABLE)
    a=assess_landed_cost(req,pa,delivery=CostLine('delivery',Money.of(2500,'EUR'),CostBasis.ESTIMATE,OBS))
    b=assess_landed_cost(req,pb,delivery=CostLine('delivery',Money.of(200,'EUR'),CostBasis.QUOTE,QUOTE))
    result=compare_cost_options((CostOption('A',a.assessment,Availability.AVAILABLE,ConfirmationState.AVAILABILITY_CONFIRMED,'same_spec'),CostOption('B',b.assessment,Availability.AVAILABLE,ConfirmationState.AVAILABILITY_CONFIRMED,'same_spec')))
    assert pa.unit_price.amount < pb.unit_price.amount
    assert a.assessment.known_total.amount == 18500
    assert b.assessment.known_total.amount == 17200
    assert result.winner_id == 'B'

def test_product_3_equipment_local_vs_remote_transport_for_8_weeks():
    local=assess_equipment(EquipmentOption('local','lift',EquipmentMode.RENT,1,Money.of(600,'EUR'),RentalRateBasis.WEEKLY,8,Availability.AVAILABLE,OBS))
    remote=assess_equipment(EquipmentOption('remote','lift',EquipmentMode.RENT,1,Money.of(430,'EUR'),RentalRateBasis.WEEKLY,8,Availability.AVAILABLE,OBS,transport=Money.of(900,'EUR')))
    r=compare_cost_options((CostOption('local',local.economic,Availability.AVAILABLE,ConfirmationState.AVAILABILITY_CONFIRMED,'lift'),CostOption('remote',remote.economic,Availability.AVAILABLE,ConfirmationState.AVAILABILITY_CONFIRMED,'lift')))
    assert local.economic.known_total.amount==4800
    assert remote.economic.known_total.amount==4340
    assert r.winner_id=='remote'

def test_product_4_hotel_vs_apartment_structure_and_local_commute_can_be_composed():
    h=AccommodationCandidate('hotel','Hotel A',AccommodationType.HOTEL,Money.of(70,'EUR'),RateBasis.ROOM_PER_NIGHT,2,OBS,ConfirmationState.AVAILABILITY_CONFIRMED,distance_to_site_km=Decimal('3'))
    a=AccommodationCandidate('apt','Apartment B',AccommodationType.APARTMENT,Money.of(140,'EUR'),RateBasis.APARTMENT_PER_NIGHT,4,OBS,ConfirmationState.AVAILABILITY_CONFIRMED,distance_to_site_km=Decimal('18'))
    ha=assess_accommodation(h,crew_size=8,nights=30,now=NOW)
    aa=assess_accommodation(a,crew_size=8,nights=30,now=NOW)
    assert ha.assessment.known_total.amount==8400
    assert aa.assessment.known_total.amount==8400
    v=VehicleEconomics(10,FuelObservation(Money.of('1.8','EUR'),'PT',OBS))
    hotel_local=assess_route_cost(RouteFacts(3,8,DistanceBasis.ROAD_PROVIDER,ROUTE),v,direction=RouteDirection.ROUND_TRIP,number_of_trips=30,tolls_known=True)
    apt_local=assess_route_cost(RouteFacts(18,25,DistanceBasis.ROAD_PROVIDER,ROUTE),v,direction=RouteDirection.ROUND_TRIP,number_of_trips=30,tolls_known=True)
    hotel_total=combine_assessments(ha.assessment,hotel_local.assessment)
    apt_total=combine_assessments(aa.assessment,apt_local.assessment)
    result=compare_cost_options((CostOption('hotel',hotel_total,Availability.AVAILABLE,ConfirmationState.AVAILABILITY_CONFIRMED,'lodging_plus_commute'),CostOption('apt',apt_total,Availability.AVAILABLE,ConfirmationState.AVAILABILITY_CONFIRMED,'lodging_plus_commute')))
    assert hotel_total.known_total.amount == Decimal('8432.40')
    assert apt_total.known_total.amount == Decimal('8594.40')
    assert result.winner_id == 'hotel'
    assert result.savings_vs_next.amount == Decimal('162.00')

def test_product_5_known_900k_with_material_unknown_is_not_true_job_cost():
    known=assess_cost_lines((CostLine('known',Money.of(900000,'EUR'),CostBasis.FACT),))
    unknown=assess_cost_lines((),unknown_components=('potential_materials_300k',))
    total=assess_true_job_cost((JobCostContribution(JobCostCategory.DIRECT_KNOWN_COST,known),JobCostContribution(JobCostCategory.MATERIAL_LANDED_COST,unknown)))
    assert total.assessment.known_total.amount==900000
    assert not total.total_job_cost_known

def test_product_6_lowest_observed_unknown_availability_is_not_confirmed_best():
    a=assess_cost_lines((CostLine('a',Money.of(100,'EUR'),CostBasis.MARKET_OBSERVATION),))
    b=assess_cost_lines((CostLine('b',Money.of(110,'EUR'),CostBasis.MARKET_OBSERVATION),))
    r=compare_cost_options((CostOption('cheap_unknown',a,Availability.UNKNOWN,ConfirmationState.AVAILABILITY_UNKNOWN,'same'),CostOption('confirmed',b,Availability.AVAILABLE,ConfirmationState.AVAILABILITY_CONFIRMED,'same')))
    assert r.winner_id=='cheap_unknown'
    assert r.status is ComparisonStatus.LOWEST_OBSERVED_AVAILABILITY_UNKNOWN

def test_product_7_eur_and_pln_are_not_summed():
    mixed=assess_true_job_cost((JobCostContribution(JobCostCategory.OTHER,assess_cost_lines((CostLine('eur',Money.of(1,'EUR'),CostBasis.FACT),))),JobCostContribution(JobCostCategory.OTHER,assess_cost_lines((CostLine('pln',Money.of(1,'PLN'),CostBasis.FACT),)))))
    assert mixed.assessment.known_total is None

def test_product_8_online_50_eur_hotel_without_rate_basis_cannot_price_crew():
    c=AccommodationCandidate('x','Online listing',AccommodationType.HOTEL,Money.of(50,'EUR'),RateBasis.UNKNOWN,None,OBS,ConfirmationState.PRICE_OBSERVED)
    a=assess_accommodation(c,crew_size=8,nights=2,now=NOW)
    assert a.assessment.known_total is None

def test_product_9_each_observed_material_euro_retains_evidence():
    req=MaterialRequirement('x','X',10,'unit',RequirementBasis.USER_SUPPLIED)
    p=MaterialPriceObservation('p','x','s','unit',Money.of(5,'EUR'),TaxBasis.VAT_INCLUDED,QUOTE,Visibility.TENANT_PRIVATE,tenant_id='tenant',availability=Availability.AVAILABLE)
    a=assess_landed_cost(req,p)
    purchase=next(line for line in a.assessment.lines if line.code=='purchase')
    assert purchase.amount.amount==50
    assert purchase.evidence is QUOTE
    assert purchase.evidence.basis is EvidenceBasis.SUPPLIER_QUOTE
