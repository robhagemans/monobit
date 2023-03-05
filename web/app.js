"use strict";

// monobit web app - hoard of bitfonts
// (c) 2023 Rob Hagemans
// licence: https://opensource.org/licenses/MIT

let pyodide = null;


function setup() {
    // reload code if listing changes
    let listing = document.getElementById("listing0");
    listing.onblur = showFont;
    setupHandlers();
    setupFonts();
    setupButtons();
    pyodide = setupPyodide();
}


///////////////////////////////////////////////////////////////////////////
// font sample


async function loadDroppedFont(file) {

    let py = await pyodide;
    let outname = file.name + '.yaff'
    py.globals.set("path", file.name);
    py.globals.set("outname", outname);
    let arraybuffer = await file.arrayBuffer();
    console.log(file.name);
    py.FS.writeFile(file.name, new Uint8Array(arraybuffer));

    let pycode = `if 1:
        import monobit
        font, *_ = monobit.load(path)
        monobit.save(font, outname, overwrite=True)
    `
    await py.runPython(pycode);

    let bytes = py.FS.readFile(outname);
    let blob = new Blob([bytes]);

    let listing = document.getElementById("listing0");
    listing.value = await blob.text();
    document.getElementById("filename").innerHTML = outname;
    showFont();
}


async function loadFont(element) {
    let blob = await blobFromGithub(element);
    let listing = document.getElementById("listing0");
    listing.value = await blob.text();
    document.getElementById("filename").innerHTML = element.path;
    showFont();
}


function clearCanvas() {
    let canvas = document.getElementById("sample");
    let context = canvas.getContext("2d");
    context.fillStyle = "black";
    context.fillRect(0, 0, canvas.width, canvas.height);
    // move to top of page instead of line of hash anchors for tabs
    window.scrollTo(0, 0);
}

function baseName(filename) {
    return filename.split("/").pop();
}

async function showFont() {
    clearCanvas();

    let canvas = document.getElementById("sample");
    let listing = document.getElementById("listing0");
    let path = baseName(document.getElementById("filename").innerHTML)
    console.log(path);
    if (!path) {
        canvas.focus();
        return;
    }
    path = "/" + path;

    let py = await pyodide;
    py.FS.writeFile(path, listing.value);
    py.globals.set("path", path);

    let pycode = `if 1:
    import js
    import monobit

    font, *_ = monobit.load(path)
    raster = monobit.chart(font, columns=32)
    #raster = monobit.render(font, sample, direction='ltr f')

    # scale for crisper result on JS canvas
    raster = raster.stretch(2, 2)

    # convert to RGBA vector
    rgba = raster.as_vector(ink=(255, 255, 255, 255), paper=(0, 0, 0, 255))

    # outputs for javascript
    rgba = bytes(_b for _e in rgba for _b in _e)
    width = raster.width
    height = raster.height
    name = font.name
    `
    await py.runPython(pycode);

    // show name as title
    let title = document.getElementById("name");
    title.innerHTML = py.globals.get("name");

    // display on canvas
    let array = new Uint8ClampedArray(
        py.globals.get("rgba").toJs()
    );
    let imagedata = new ImageData(
        array, py.globals.get("width"), py.globals.get("height")
    );
    let context = canvas.getContext("2d");

    // resize canvas to fit width
    canvas.width = imagedata.width;
    canvas.height = Math.floor(imagedata.width * 3 / 4);
    clearCanvas();

    context.putImageData(imagedata, 0, 0);
    canvas.focus();
}


///////////////////////////////////////////////////////////////////////////
// event handlers

function setupButtons() {
    //
    // conversion/download buttons
    //
    document.getElementById("dl-mzfon").onclick = () => { download('fon', 'mzfon') };
    document.getElementById("dl-bdf").onclick = () => { download('bdf', 'bdf') };
    document.getElementById("dl-yaff").onclick = () => { download('yaff') };
}



function setupHandlers() {
    //
    // handlers to load files on drag & drop
    //

    function nop(e) {
        e.stopPropagation();
        e.preventDefault();
    }

    function drop(e) {
        e.stopPropagation();
        e.preventDefault();
        let files = e.dataTransfer.files;
        loadDroppedFont(files[0]);
    }

    let canvas = document.getElementById("sample");
    canvas.addEventListener("dragenter", nop);
    canvas.addEventListener("dragover", nop);
    canvas.addEventListener("drop", drop);

    var listing = document.getElementById("listing0");
    listing.addEventListener("dragenter", nop);
    listing.addEventListener("dragover", nop);
    listing.addEventListener("drop", drop);

    var storage = document.getElementById("font-list");
    storage.addEventListener("dragenter", nop);
    storage.addEventListener("dragover", nop);
    storage.addEventListener("drop", drop);
}


///////////////////////////////////////////////////////////////////////////////
// font collection

async function setupFonts() {
    //
    // retrieve font list from Github and show
    //
    let tree = await fontListFromGithub();
    buildCollection(tree);

    // bring fonts list to front
    location.hash = "#fonts";
}


function buildCollection(collection) {
    //
    // show list of available fonts
    // structure: ul > li > ol > li
    //
    let parent = document.getElementById("font-list");
    let ul = parent.appendChild(document.createElement("ul"))
    let ulli = document.createElement("li");
    let ol = document.createElement("ol");

    function attachList() {
        // attach last subdirectory list, if not empty
        if (ol.children.length) {
            ul.appendChild(ulli).appendChild(ol);
        }
    }

    for(let element of collection) {
        if (element.type == "tree") {
            attachList();
            ulli = document.createElement("li");
            ulli.innerHTML = "&nbsp;&#x2605; " + element.path;
            ol = document.createElement("ol");
        }
        else if (element.path.endsWith('.yaff') || element.path.endsWith('.draw')) {
            let li = ol.appendChild(document.createElement("li"));
            li.appendChild(createDownloadLink(element));
            li.appendChild(createPlayLink(element));
        }
    }
    attachList();
}

function createDownloadLink(element) {
    //
    // create download link to file
    //
    let a = document.createElement("a");
    a.innerHTML = "&#9662;";
    a.className = "hidden download";
    a.onclick = () => { downloadFromGithub(element); return false; };
    return a;
}

function createPlayLink(element) {
    //
    // create "play" / show-font link
    //
    let play = document.createElement("a");
    play.innerHTML = '<span class="hidden">&#9656;</span> ' + baseName(element.path);
    play.className = "run";
    play.onclick = () => { loadFont(element); return false; };
    return play;
}



function downloadBytes(name, blob) {
    //
    // download binary content
    //
    //let blob = new Blob([bytes]);
    // create another anchor and trigger download
    let a = document.createElement("a");
    a.className = "hidden download";
    a.download = baseName(name);
    a.href = window.URL.createObjectURL(blob);
    // trigger download
    a.click();
    a.remove();
}


///////////////////////////////////////////////////////////////////////////////
// Github interface

async function fontListFromGithub() {
    //
    // retrieve font list from Github
    //
    let tree = null;
    let refreshTime = JSON.parse(localStorage.getItem("refresh_time"));
    // hit github no more than once per hour (rate limit)
    if (refreshTime && Date.now() - refreshTime < 3.6e+6) {
        tree = JSON.parse(localStorage.getItem("github_tree"));
    }
    if (!tree) {
        console.log('refresh github tree');
        let url = "https://api.github.com/repos/robhagemans/hoard-of-bitfonts/git/trees/master?recursive=1";
        tree = await fetch(url)
            .then((response) => response.json())
            .then((result) => result.tree);
        localStorage.setItem("github_tree", JSON.stringify(tree));
        localStorage.setItem("refresh_time", JSON.stringify(Date.now()));
    }
    return tree;
}

async function downloadFromGithub(element) {
    //
    // user download of file from Github
    //
    let blob = await blobFromGithub(element);
    downloadBytes(element.path, blob);
    // do not follow link
    return false;
}

async function blobFromGithub(element) {
    //
    // get file from Github as blob
    //
    // use raw link instead of api link to avoid rate limit
    let url = 'https://raw.githubusercontent.com/robhagemans/hoard-of-bitfonts/master/' + element.path;
    let response = await fetch(url);
    let blob = await response.blob();
    return blob;
}


///////////////////////////////////////////////////////////////////////////////
// conversions

async function download(suffix, format) {

    let listing = document.getElementById("listing0");
    let path = "/" + baseName(document.getElementById("filename").innerHTML);
    console.log(path);

    let outname = path.split(".")[0] + '.' + suffix

    let py = await pyodide;
    py.FS.writeFile(path, listing.value);
    py.globals.set("path", path);
    py.globals.set("outname", outname);
    py.globals.set("format", format);

    let pycode = `if 1:
        import monobit
        font, *_ = monobit.load(path)
        monobit.save(font, outname, format=format, overwrite=True)
    `
    await py.runPython(pycode);

    let bytes = py.FS.readFile(outname);
    let blob = new Blob([bytes]);
    downloadBytes(outname, blob);
}


///////////////////////////////////////////////////////////////////////////////
// pyodide

async function setupPyodide() {
    let pyodide = await loadPyodide();
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");
    // do not await optional format dependencies
    await Promise.all([
        micropip.install("monobit", /*keep_going*/ true, /*deps*/ false),
    ]);
    micropip.install("lzma")
    console.log('Pyodide setup complete.')
    clearCanvas();
    document.getElementById("name").innerHTML = "Drop a font file - or choose from the Hoard"
    return pyodide;
}


///////////////////////////////////////////////////////////////////////////////
// kludge to use he #targets while keeping a top margin

window.addEventListener("hashchange", function () {
    window.scrollTo(0, 0);
});
