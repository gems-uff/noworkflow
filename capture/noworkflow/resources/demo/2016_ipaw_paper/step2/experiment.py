import sys
from external import align_warp, reslice, softmean, slicer
from convert import pgmtoppm, pnmtojpeg

def align_reslice(anatomy_image, reference_image):
    anatomy_header = anatomy_image[:-3] + "hdr"
    reference_header = reference_image[:-3] + "hdr"
    warp = align_warp(anatomy_image, anatomy_header,
                      reference_image, reference_header)
    return reslice(warp)

def slice_convert(atlas_image, atlas_header, coordinate):
    atlas_slice = slicer(atlas_image, atlas_header, coordinate)
    return pnmtojpeg(pgmtoppm(atlas_slice))

def main():
    reference = sys.argv[-1]
    anatomy_images = sys.argv[1:-1]
    resliced = []
    for anatomy in anatomy_images:
        resliced += align_reslice(anatomy, reference)
    atlas_image, atlas_header = softmean(*resliced)
    for coordinate in ["x", "y", "z"]:
        atlas = slice_convert(atlas_image, atlas_header, coordinate)

main()
