from fastapi import APIRouter, Depends

from app.auth import CurrentUser, require_admin
from app.services.clinic_service import (
    ClinicProfile,
    get_clinic_profile,
    update_clinic_profile,
)

router = APIRouter(prefix="/clinic", tags=["clinic"])


@router.get("")
async def read_clinic(_: CurrentUser = Depends(require_admin)):
    return await get_clinic_profile()


@router.put("")
async def write_clinic(
    profile: ClinicProfile,
    _: CurrentUser = Depends(require_admin),
):
    return await update_clinic_profile(profile)
