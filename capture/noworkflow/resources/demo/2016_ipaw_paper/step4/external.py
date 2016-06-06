# Dummy calls for representing openings

def align_warp(anatomy_image, anatomy_header, ref_image, ref_header):
    with open(anatomy_image, "rb"), open(anatomy_header, "rb"), \
            open(ref_image, "rb"), open(ref_header, "rb"), \
            open("warp.warp", "wb") as warp:
        if anatomy_image == "anatomy1.img":
            warp.write(b"\x01\x00\x00\x00\x04\x00\x00\x00")
        if anatomy_image == "anatomy2.img":
            warp.write(b"\x02\x00\x00\x00\x04\x00\x00\x00")
        if anatomy_image == "anatomy3.img":
            warp.write(b"\x03\x00\x00\x00\x04\x00\x00\x00")
        if anatomy_image == "anatomy4.img":
            warp.write(b"\x04\x00\x00\x00\x04\x00\x00\x00")
        return "warp.warp"

def reslice(warp, num=[1]):
    image = "reslice{}.img".format(num[0])
    header = "reslice{}.hdr".format(num[0])
    with open(warp, "rb") as w, \
            open(image, "w") as ri, open(header, "w") as rh:
        ri.write("image " + str(num[0]))
        rh.write("header " + str(num[0]))
    num[0] += 1
    return image, header

def softmean(rimag1, rhead1, rimag2, rhead2, rimag3, rhead3, rimag4, rhead4):
    with open(rimag1, "rb"), open(rhead1, "rb"), \
            open(rimag2, "rb"), open(rhead2, "rb"), \
            open(rimag3, "rb"), open(rhead3, "rb"), \
            open(rimag4, "rb"), open(rhead4, "rb"), \
            open("atlas.img", "w") as atlas_i, \
            open("atlas.hdr", "w") as atlas_h:
        atlas_i.write("atlas image")
        atlas_h.write("atlas header")
    return "atlas.img", "atlas.hdr"

def slicer(atlas_image, atlas_header, coordinate):
    output = "atlax-{}.pgm".format(coordinate)
    with open(atlas_image, "rb"), open(atlas_header, "rb"), \
            open(output, "w") as aslice:
        aslice.write("atlas {}".format(coordinate))
    return output

def convert(atlas_slice):
    result = atlas_slice[:-3] + "gif"
    with open(atlas_slice, "rb") as aslice, \
            open(result, "w") as gif:
        gif.write(atlas_slice)
    return result
