from io import BytesIO

import qrcode
from django.core.files.base import ContentFile


def generate_qr_code(boarding_pass):
    """Save a PNG QR code containing only the boarding pass UUID."""
    if boarding_pass.qr_code_image and boarding_pass.qr_code_image.storage.exists(
        boarding_pass.qr_code_image.name
    ):
        return boarding_pass.qr_code_image

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(str(boarding_pass.pass_code))
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    image_buffer = BytesIO()
    image.save(image_buffer, format="PNG")
    filename = f"boarding_pass_{boarding_pass.pass_code}.png"
    boarding_pass.qr_code_image.save(
        filename,
        ContentFile(image_buffer.getvalue()),
        save=True,
    )
    return boarding_pass.qr_code_image
