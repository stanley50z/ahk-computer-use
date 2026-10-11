// Save/export the test's Pen-created fixture without changing its geometry; never supplied to an actor.
(function () {
    var log = new File(config.result);
    try {
        var doc = app.activeDocument;
        if (doc.fullName.fsName !== new File(config.starter).fsName) throw new Error('Unexpected active document');
        if (doc.pathItems.length !== 1) throw new Error('Expected one Pen-created path');
        var path = doc.pathItems[0];
        var blue = new RGBColor(); blue.red = 0; blue.green = 174; blue.blue = 239;
        path.filled = true; path.fillColor = blue; path.stroked = false;
        var save = new IllustratorSaveOptions(); save.pdfCompatible = true;
        doc.saveAs(new File(config.ai), save);
        var png = new ExportOptionsPNG24();
        png.artBoardClipping = true; png.transparency = false; png.antiAliasing = true;
        png.horizontalScale = 100; png.verticalScale = 100; png.interlaced = false;
        doc.exportFile(new File(config.png), ExportType.PNG24, png);
        log.open('w'); log.write('SUCCESS'); log.close();
    } catch (error) {
        log.open('w'); log.write('ERROR: ' + error + '\n' + $.stack); log.close();
    }
}());
