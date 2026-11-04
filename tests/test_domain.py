from decimal import Decimal
import pytest
from app.domain import money, decimal, date, net_weight, RuleError, posting, event

@pytest.mark.parametrize('value,unit,expected',[('۱٬۰۰۰','IRR',1000),('12.3','IRT',123),('0','IRR',0),('۱۰۰','IRT',1000)])
def test_money(value,unit,expected):assert money(value,unit)==expected
@pytest.mark.parametrize('value',['NaN','Infinity','-1','0.5','100000000000000'])
def test_bad_money(value):
    with pytest.raises(RuleError):money(value)
@pytest.mark.parametrize('value',['14050231','۱۴۰۵/۰۸/۱۳','14031230'])
def test_valid_dates(value):assert date(value)>0
@pytest.mark.parametrize('value',['14051230','14050731','14051301','x','2026-11-04','14050232'])
def test_invalid_dates(value):
    with pytest.raises(RuleError):date(value)
def test_net_zero_override_and_floor():
    assert net_weight('100','10','0','0','0')==100
    assert net_weight('100','10','1.4','0','0')==85
    assert net_weight('1000','10','1','2','1')==965
@pytest.mark.parametrize('args',[('10','2',None),('10','100','1'),('10','1.1','1'),('10','1','1','101')])
def test_bad_net(args):
    with pytest.raises(RuleError):net_weight(*args)
def test_balanced_posting():
    lines=posting({'kind':'فروش','amount':100000,'cost':70000})
    assert len(lines)==4 and sum(x['debit'] for x in lines)==sum(x['credit'] for x in lines)==170000
