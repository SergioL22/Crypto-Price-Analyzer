from datetime import datetime,timezone
import pytest
from pydantic import ValidationError
from account_models import Workspace

ASSET='twelvedata:stock:XNYS:USD:ABC'
def workspace(saved=None):
    listing={'id':ASSET,'name':'Example'}
    if saved is not None:listing['saved_on']=saved
    return {'version':1,'listings':[listing],'holdings':[],'alerts':[]}

def test_legacy_account_backup_shape_is_preserved():
    data=workspace()
    assert Workspace.model_validate(data).model_dump()==data

def test_browser_tracking_date_survives_account_import_roundtrip():
    data=workspace(datetime.now(timezone.utc).date().isoformat())
    assert Workspace.model_validate(data).model_dump()==data

@pytest.mark.parametrize('saved',['2026-02-30','2999-01-01','20261001',True])
def test_invalid_tracking_dates_are_rejected(saved):
    with pytest.raises(ValidationError):Workspace.model_validate(workspace(saved))
