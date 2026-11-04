"""The same display function runs in central forms, read-only reports and offline HTML."""
from pathlib import Path
import shutil,subprocess
import pytest

def test_shared_currency_exact_display():
    if not shutil.which('node'):pytest.skip('Node is needed for browser-side arithmetic tests')
    js=r"""
const assert=require('assert'),M=require('./static/currency.js');
const normalize=s=>s.replace(/[۰-۹]/g,x=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(x))).replace(/٬/g,'').replace(/٫/g,'.');
const cfg={report_currency:'USD',display_decimals:'2'},curr=[{id:'USD',name:'دلار',rial_per_unit:'600000'}];
assert.equal(normalize(M.format('12345678901','AUTO',cfg,curr)),'20576.13');
assert.equal(normalize(M.format('-1','AUTO',cfg,curr)),'0.00');
assert.equal(normalize(M.format('15','IRT',cfg,curr)),'1.5');
assert.equal(normalize(M.format('999999999999999','IRR',cfg,curr)),'999999999999999');
assert.equal(normalize(M.format('3','USD',{},[{id:'USD',rial_per_unit:'2'}])),'1.50');
assert.equal(normalize(M.format('1','USD',{},[{id:'USD',rial_per_unit:'0.1'}])),'10.00');
assert(M.format('1','USD',{},[]).includes('نرخ ثبت نشده'));
assert(M.format('1','USD',{},[{id:'USD',rial_per_unit:'0'}]).includes('نرخ نامعتبر'));
assert(M.format('1','USD',{},[{id:'USD',rial_per_unit:'1e-8'}]).includes('نرخ ثبت نشده'));
assert.equal(M.view('AUTO',[{key:'report_currency',value:'IRT'}],[]).name,'تومان');
assert.equal(M.view('USD',{display_decimals:'3.5'},curr).digits,2);
"""
    subprocess.run(['node','-e',js],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True,text=True)
