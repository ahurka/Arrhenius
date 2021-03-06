from flask import request, jsonify, send_from_directory
from typing import Optional
from website import app

from os import path
from pathlib import Path

from threading import Lock
import shutil

from core.configuration import from_json_string, ArrheniusConfig, InvalidConfigError
from core.output_config import ReportDatatype, default_output_config
from runner import ModelRun

from data.display import OUTPUT_FULL_PATH, save_from_dataset,\
    image_file_name, get_image_directory
from data.provider import PROVIDERS


# A lock that protects the image file system from concurrent access.
# Prevents image writing from being interrupted by a subsequent call
# on the same dataset.
# Consider replacing with one lock per set of run IDs, for improved
# concurrency.
img_fs_lock = Lock()

var_name_to_output_type = {
    output_type.value: output_type for output_type in ReportDatatype
}

# A dictionary illustrating proper ranges of values for model config options.
example_config = {
    "co2": {
        "from": [1],
        "to": [0.67, 1.0, 1.5, 2.0, 2.5, 3.0]
    },
    "year": "int",
    "grid": {
        "dims": {
            "lat": "(0, 180]",
            "lon": "(0, 360]"
        },
        "repr": ["count", "width"]
    },
    "layers": "<int >= 1>",
    "iters": "<int >= 0>",
    "aggregate_lat": ["before", "after", "none"],
    "aggregate_level": ["before", "after", "none"],
    "temp_src": [func_name for func_name in PROVIDERS['temperature']],
    "humidity_src": [func_name for func_name in PROVIDERS['humidity']],
    "albedo_src": [func_name for func_name in PROVIDERS['albedo']],
    "pressure_src": [func_name for func_name in PROVIDERS['pressure']],
    "absorbance_src": ["table", "modern", "multilayer"],
    "CO2_weight": ["closest", "low", "high", "mean"],
    "H2O_weight": ["closest", "low", "high", "mean"],
    "scale": ["<number>", "<number>"],
}


def ensure_model_results(config: 'ArrheniusConfig') -> (str, bool):
    """
    Guarantee that the model run with configuration options given by config
    has been run, and its output is present on disk. Returns a full path to
    the output directory, followed by a boolean flag that is True iff a new
    model run was required to compute the results; that is, the results were
    not already cached.

    If a model run has been previously made on the same configuration as
    config and the results of this run are still locally available, then no
    model runs or other computationally-intensive steps will be taken.
    However, if the specific configuration options have not been received
    before, or their results erased from disk, then the model run may be
    very time-intensive.

    :param config:
        Configuration for the model run
    :return:
        A 2-tuple containing a path to the output directory, followed by
        whether the model output was not already on disk.
    """
    run_id = str(config.run_id())
    dataset_parent = path.join(OUTPUT_FULL_PATH, run_id)
    created = False

    if not Path(dataset_parent).exists():
        # Model run on the provided configuration options has not been run;
        # run it, producing the output directory as well as image files for
        # the requested variable.
        output_center = default_output_config()

        run = ModelRun(config, output_center)
        run.run_model()
        created = True

    return dataset_parent, created


def ensure_image_output(ds_parent: str,
                        var_name: str,
                        time_seg: Optional[int],
                        config: 'ArrheniusConfig') -> (str, bool):
    """
    Guarantee that an image file has been produced representing the
    time_seg'th time unit of variable var_name from the NetCDF dataset
    file contained in path ds_parent, presumably produced by a previous
    model run. Returns a path to the directory containing the image,
    as well as a boolean flag that is True iff the image was created.

    config provides some additional information that is useful for
    identifying names of files and directories. It is not used to launch
    any new model runs. Namely, if a dataset has not been created inside
    directory ds_parent, then no new dataset will be created, and this
    function will fail.

    :param ds_parent:
        A path to the directory containing a dataset to pull data from
    :param var_name:
        The name of the variable in the dataset that is to be rendered
    :param time_seg:
        The time unit from which data is to be extracted
    :param config:
        Additional configuration options specifying model run details
    :return:
        A 2-tuple containing a path to the directory containing the image,
        followed by whether the image was not already on disk.
    """
    created = save_from_dataset(ds_parent, var_name, time_seg,
                                config)
    img_parent = get_image_directory(ds_parent, config.run_id(), var_name,
                                     config.colorbar(), create=False)

    return img_parent, created


@app.route('/model/help', methods=['GET'])
def config_options():
    """
    Returns a response to an HTTP request for example configuration options.

    If the request is a GET request, the response contains a template for
    a configuration dictionary, most of the keys of which point to strings
    or lists that specify the range of values acceptable for that key.

    :return:
        An HTTP response containing an example configuration dictionary.
    """
    return jsonify(example_config), 200


@app.route('/model/dataset', methods=['POST'])
def scientific_dataset():
    """
    Returns a response to an HTTP request for the NetCDF dataset associated
    with a specified set of model configuration options.

    If the request is a POST request, a configuration dictionary is expected
    in the request body in the form of a JSON string. Assuming the
    configuration options are valid, the dataset object will be returned that
    was produced by a model run using the specified configuration options.

    :return:
        An HTTP response with the requested dataset attached
    """
    # Decode JSON string from request body.
    config = from_json_string(request.data.decode("utf-8"))
    run_id = str(config.run_id())
    dataset_name = run_id + ".nc"

    # Check to make sure the requested dataset is available on disk,
    # create it if necessary.
    dataset_parent, created = ensure_model_results(config)
    response_code = 201 if created else 200

    # Send the dataset file attached to the HTTP response.
    return send_from_directory(dataset_parent, dataset_name), response_code


@app.route('/model/<varname>/<time_seg>', methods=['POST'])
def single_model_data(varname: str, time_seg: str):
    """
    Returns a response to an HTTP request for one image file produced by
    a run of the Arrhenius model, that is associated with variable varname
    and the time unit time_seg (or 0 for average over all time segments).

    If the request is a POST request, a configuration dictionary is expected
    in the request body in the form of a JSON string. Assuming the
    configuration options are valid, an image file will be attached to the
    response that represents a map of the globe, overlaid with the results
    of a model run with the given configuration options.

    More specifically, the image file is the time_seg'th map produced for
    variable varname under the relevant model run.

    :param varname:
        The name of the variable that is overlaid on the map
    :param time_seg:
        A specifier for which month, season, or general time gradation
        the map should represent
    :return:
        An HTTP response with the requested image file attached as raw data
    """
    # Decode JSON string from request body.
    config = from_json_string(request.data.decode("utf-8"))

    parent_dir, model_created = ensure_model_results(config)

    # Find and access the requested image file, or create it if necessary.
    img_fs_lock.acquire()
    download_path, img_created = ensure_image_output(parent_dir, varname,
                                                     int(time_seg), config)
    img_fs_lock.release()

    # Get the file's name and path in preparation for sending to the client.
    base_name = varname + "_" + str(time_seg)
    file_name = image_file_name(base_name, config) + ".png"

    # Send the HTTP response with the file contents in its body.
    response_code = 201 if model_created or img_created else 200
    return send_from_directory(download_path, file_name), response_code


@app.route('/model/<varname>', methods=['POST'])
def multi_model_data(varname: str):
    """
    Returns a response to an HTTP request for all image files produced by
    a run of the Arrhenius model, that are associated with variable varname.

    If the request is a POST request, a configuration dictionary is expected
    in the request body in the form of a JSON string. Assuming the
    configuration options are valid, a zip archive will be attached to the
    response that contains all image maps that are overlaid with variable
    varname.

    :param varname:
        The name of the variable that is overlaid on the map
    :return:
        An HTTP response with requested image files attached, in a zip file
    """
    # Decode JSON string from request body.
    config = from_json_string(request.data.decode("utf-8"))
    run_id = str(config.run_id())

    # This series of zip-file-related variables makes the purpose of each
    # expression more recognizable, but they are not really necessary.
    scale_suffix = "[{}x{}]".format(*config.colorbar())
    scale_dir_name = "_".join([run_id, scale_suffix])
    archive_name = "_".join([run_id, varname, scale_suffix])

    ds_parent, model_created = ensure_model_results(config)
    archive_path = path.join(ds_parent, scale_dir_name, archive_name)

    img_created = False
    if not Path(archive_path + ".zip").is_file():
        # The zip file has not been made yet: create all image files
        # for all time units with the requested variable and zip them.
        archive_src, img_created = ensure_image_output(ds_parent, varname,
                                                       None, config)
        shutil.make_archive(archive_path, 'zip', archive_src)

    # Send the zip file attached to the HTTP response.
    response_code = 201 if model_created or img_created else 200
    return send_from_directory(ds_parent, archive_name + ".zip"),\
        response_code


def error_template(title: str,
                   msg: str) -> str:
    """
    Returns HTML markup reporting an error. title is written in a header,
    and msg is written in a body text block beneath.

    :param title:
        Text for the header of the HTML page
    :param msg:
        Text for the body of the HTML page
    :return:
        A string containing HTML markup
    """
    head = "<DOCTYPE html>" \
           + "\n<head>" \
           + "\n  <title>" + title + "</title>" \
           + "\n</head>"
    body = "<body>" \
           + "\n  <h1>" + title + "</h1>" \
           + "\n  <hr>" \
           + "\n  <p>" + msg + "</p>" \
           + "\n</body>"

    markup = head + "\n" + body
    return markup


@app.errorhandler(InvalidConfigError)
def handle_invalid_config(err: InvalidConfigError):
    """
    Handler for InvalidConfigError, producing an HTML page whenever an API
    endpoint encounters an error of that type. This page reports details of
    which part of the configuration was invalid.

    :param err:
        The InvalidConfigError that triggered the handler
    :return:
        An HTTP response to send to the client
    """
    return error_template("Invalid Configuration", str(err)), 400


@app.errorhandler(IOError)
def handle_enomem(err: IOError):
    """
    Handler for IOErrors in the server, producing an HTML page whenever an API
    endpoint encounters an error of that type. This page reports whether the
    error was caused by lack of disk space.

    :param err:
        The IOError that triggered the handler
    :return:
        An HTTP response to send to the client
    """
    if err.errno == 28:
        msg = "The server has insufficient disk space to produce output" \
              " from a model run, and has failed to either produce a dataset" \
              " for model results or to write image files from said results." \
              " Consider placing a request for fewer resources at a time to" \
              " lighten the load on server while it tries to free up space."
        return error_template("Insufficient Space", msg), 413
    else:
        msg = "The server has failed to perform disk IO, most likely due to a" \
              " malformed path. Please report this error to project engineers."
        return error_template("Failed Disk IO", msg), 500


@app.errorhandler(500)
def handle_failure(err):
    """
    Handler for any server error that would ordinarily cause a response to be
    sent with HTTP code 500. Produces an HTML page whenever an API endpoint
    encounters an error of that type. This page currently does not provide any
    useful information to the user, but it can be styled in the future.

    :param err:
        The error that triggered the handler
    :return:
        An HTTP response to send to the client
    """
    msg = "We are sorry, but our server is still young and has experienced an" \
          " unexpected error. Please report this error to project engineers to" \
          " get it patched sooner."
    return error_template("Internal Error", msg), 500
