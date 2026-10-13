// Set up the test's Pen-created drawing appearance; no save/export or geometry changes, never supplied to an actor.
(function () {
    var log = new File(config.result);
    try {
        var doc = app.activeDocument;
        if (doc.fullName.fsName !== new File(config.starter).fsName) throw new Error('Unexpected active document');
        if (doc.pathItems.length !== 1) throw new Error('Expected one Pen-created path');
        var path = doc.pathItems[0];
        var blue = new RGBColor(); blue.red = 0; blue.green = 174; blue.blue = 239;
        path.filled = true; path.fillColor = blue; path.stroked = false;
        // A hidden reference is ordinary tracing material, not final drawing output or a new method restriction.
        var reference = doc.placedItems.add();
        reference.file = new File(config.reference);
        reference.position = [0, 800];
        reference.hidden = true;
        var pasteboardReference = doc.placedItems.add();
        pasteboardReference.file = new File(config.reference);
        pasteboardReference.position = [900, 800];
        log.encoding = 'UTF-8';
        log.open('w'); log.write('SUCCESS'); log.close();
    } catch (error) {
        log.encoding = 'UTF-8';
        log.open('w'); log.write('ERROR: ' + error + '\n' + $.stack); log.close();
    }
}());
