from .nowkernel import NowKernel

if __name__ == '__main__':
    from ipykernel import kernelapp as app
    app.launch_new_instance(kernel_class=NowKernel)