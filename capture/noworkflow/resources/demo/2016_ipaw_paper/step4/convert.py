# Dummy calls for representing openings

def pgmtoppm(atlas_slice):
    result = atlas_slice[:-3] + "ppm"
    with open(atlas_slice, "rb") as aslice, \
            open(result, "w") as gif:
        gif.write(atlas_slice + ".ppm")
    return result

def pnmtojpeg(ppm_slice):
    result = ppm_slice[:-3] + "jpg"
    with open(ppm_slice, "rb") as aslice, \
            open(result, "w") as gif:
        gif.write(ppm_slice + ".jpg")
    return result
