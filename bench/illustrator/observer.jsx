// Maintainer-only document preparation, saved-file inspection and guarded cleanup. The wrapper supplies config.
(function () {
    function encode(value) {
        if (value === null) return 'null';
        if (typeof value === 'string') return '"' + value.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\r/g, '\\r').replace(/\n/g, '\\n').replace(/\t/g, '\\t') + '"';
        if (typeof value === 'number' || typeof value === 'boolean') return String(value);
        var parts = [], i;
        if (value instanceof Array) {
            for (i = 0; i < value.length; i++) parts.push(encode(value[i]));
            return '[' + parts.join(',') + ']';
        }
        for (i in value) if (value.hasOwnProperty(i)) parts.push(encode(i) + ':' + encode(value[i]));
        return '{' + parts.join(',') + '}';
    }
    // Fingerprint geometry and common appearance/text properties without serializing mutable viewport/selection state.
    function artworkSignature(doc) {
        var state = [], i, j;
        for (i = 0; i < doc.artboards.length; i++) state.push(doc.artboards[i].artboardRect);
        for (i = 0; i < doc.layers.length; i++) state.push([doc.layers[i].name, doc.layers[i].visible, doc.layers[i].locked]);
        for (i = 0; i < doc.pageItems.length; i++) {
            var item = doc.pageItems[i];
            state.push([item.typename, item.name, item.geometricBounds, item.opacity, item.hidden, item.locked]);
            if (item.typename === 'PathItem') {
                state.push([item.closed, item.filled, item.stroked, item.strokeWidth]);
                for (j = 0; j < item.pathPoints.length; j++)
                    state.push([item.pathPoints[j].anchor, item.pathPoints[j].leftDirection, item.pathPoints[j].rightDirection]);
                var color = item.fillColor;
                if (color.typename === 'RGBColor') state.push([color.typename, color.red, color.green, color.blue]);
                else if (color.typename === 'CMYKColor') state.push([color.typename, color.cyan, color.magenta, color.yellow, color.black]);
                else if (color.typename === 'GrayColor') state.push([color.typename, color.gray]);
                else state.push(color.typename);
            } else if (item.typename === 'TextFrame') state.push(item.contents);
        }
        var text = encode(state), hash = 2166136261;
        for (i = 0; i < text.length; i++) {
            hash ^= text.charCodeAt(i);
            hash = (hash + (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24)) >>> 0;
        }
        return String(hash);
    }
    function info(doc) {
        var path = '';
        try { path = doc.fullName.fsName; } catch (error) { /* Unsaved documents have no fullName. */ }
        return {path: path, name: doc.name, saved: doc.saved, page_items: doc.pageItems.length,
                artwork_signature: artworkSignature(doc)};
    }
    function documents() {
        var values = [];
        for (var i = 0; i < app.documents.length; i++) values.push(info(app.documents[i]));
        return values;
    }
    function key(value) { return value.path ? new File(value.path).fsName.toLowerCase() : 'unsaved:' + value.name; }
    function assertProtected(current) {
        var seen = {}, lists = [config.before, current];
        for (var n = 0; n < lists.length; n++) {
            seen = {};
            for (var m = 0; m < lists[n].length; m++) {
                var identity = '$' + key(lists[n][m]);
                if (seen[identity]) throw new Error('Ambiguous document identity; refusing cleanup');
                seen[identity] = true;
            }
        }
        for (var i = 0; i < config.before.length; i++) {
            var found = false;
            for (var j = 0; j < current.length; j++) if (key(config.before[i]) === key(current[j])) found = true;
            if (!found) throw new Error('Pre-existing document disappeared or was renamed; refusing cleanup');
        }
    }
    var preferenceTypes = {ResolutionR: 'Real', AntiAlias: 'Integer', BackgroundTransparent: 'Boolean', Interlaced: 'Boolean',
                           'Background/red': 'Integer', 'Background/green': 'Integer', 'Background/blue': 'Integer'};
    function pngPreferences() {
        var values = {};
        for (var name in preferenceTypes) if (preferenceTypes.hasOwnProperty(name))
            values[name] = app.preferences['get' + preferenceTypes[name] + 'Preference']('plugin/PNGFileFormat/' + name);
        return values;
    }
    function setPngPreferences(values) {
        for (var name in preferenceTypes) if (preferenceTypes.hasOwnProperty(name))
            app.preferences['set' + preferenceTypes[name] + 'Preference']('plugin/PNGFileFormat/' + name, values[name]);
    }
    var log = new File(config.result), result, doc = null;
    try {
        if (config.phase === 'snapshot') {
            result = {documents: documents(), png_preferences: pngPreferences()};
        } else if (config.phase === 'prepare') {
            var before = documents();
            for (var i = 0; i < before.length; i++) if (key(before[i]) === new File(config.starter).fsName.toLowerCase())
                throw new Error('Task starter is already open; refusing reuse');
            doc = app.open(new File(config.starter));
            if (doc.documentColorSpace !== DocumentColorSpace.RGB || doc.artboards.length !== 1 || doc.pageItems.length !== 0)
                throw new Error('Starter is not a blank single-artboard RGB document');
            var rect = doc.artboards[0].artboardRect;
            if (rect[2] - rect[0] !== 800 || rect[1] - rect[3] !== 800) throw new Error('Starter dimensions changed');
            doc.activate();
            if (!app.switchWorkspace('Getting Started') || !app.resetWorkspace()) throw new Error('Cannot establish the benchmark workspace');
            setPngPreferences({ResolutionR: 72, AntiAlias: 1, BackgroundTransparent: false, Interlaced: false,
                               'Background/red': 65535, 'Background/green': 65535, 'Background/blue': 65535});
            doc.views[0].zoom = 1;
            doc.views[0].centerPoint = [(rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2];
            app.redraw();
            result = {before: before, documents: documents(), zoom: doc.views[0].zoom,
                      center: doc.views[0].centerPoint, artboard: rect, workspace: 'Getting Started', png_preferences: pngPreferences()};
            doc = null; // Leave the task document open for the actor.
        } else if (config.phase === 'verify') {
            var inspection = new File(config.inspection);
            var opened = documents();
            for (var i = 0; i < opened.length; i++) if (key(opened[i]) === inspection.fsName.toLowerCase())
                throw new Error('Inspection copy is already open; refusing reuse');
            doc = app.open(inspection);
            var rect = doc.artboards[0].artboardRect;
            var checks = {artboard: doc.documentColorSpace === DocumentColorSpace.RGB && doc.artboards.length === 1 &&
                          rect[2] - rect[0] === 800 && rect[1] - rect[3] === 800,
                          editable_paths: doc.pathItems.length > 0 && doc.rasterItems.length === 0 && doc.placedItems.length === 0,
                          appearance: true};
            var types = {}, paths = [];
            for (var i = 0; i < doc.pageItems.length; i++) {
                var item = doc.pageItems[i];
                types[item.typename] = (types[item.typename] || 0) + 1;
                if (item.typename !== 'PathItem' && item.typename !== 'CompoundPathItem' && item.typename !== 'GroupItem') checks.editable_paths = false;
                if (item.hidden || item.opacity !== 100) checks.appearance = false;
            }
            for (var i = 0; i < doc.layers.length; i++) if (!doc.layers[i].visible) checks.appearance = false;
            for (var i = 0; i < doc.pathItems.length; i++) {
                var path = doc.pathItems[i], fill = path.fillColor;
                if (path.guides || !path.filled || path.stroked || fill.typename !== 'RGBColor' ||
                    Math.abs(fill.red) > 0.5 || Math.abs(fill.green - 174) > 0.5 || Math.abs(fill.blue - 239) > 0.5)
                    checks.appearance = false;
                var points = [];
                for (var j = 0; j < path.pathPoints.length; j++) points.push({anchor: path.pathPoints[j].anchor,
                    left: path.pathPoints[j].leftDirection, right: path.pathPoints[j].rightDirection});
                paths.push({anchors: path.pathPoints.length, closed: path.closed, points: points});
            }
            var options = new ExportOptionsPNG24();
            options.artBoardClipping = true;
            options.horizontalScale = 100; options.verticalScale = 100;
            options.antiAliasing = true; options.transparency = false;
            options.interlaced = false;
            doc.exportFile(new File(config.render), ExportType.PNG24, options);
            result = {checks: checks, item_types: types, paths: paths, artboard: rect};
        } else if (config.phase === 'cleanup') {
            var current = documents();
            assertProtected(current);
            // Revalidate every document and the full close set before closing even one.
            for (var i = 0; i < current.length; i++) {
                var protectedDoc = false, allowed = false;
                for (var j = 0; j < config.before.length; j++) if (key(current[i]) === key(config.before[j])) protectedDoc = true;
                for (var j = 0; j < config.close.length; j++) if (key(current[i]) === new File(config.close[j]).fsName.toLowerCase()) allowed = true;
                if (!protectedDoc && !allowed) throw new Error('Unclaimed Illustrator document; refusing cleanup: ' + current[i].name);
                if (protectedDoc && allowed) throw new Error('Refusing to close a pre-existing document');
            }
            for (var i = app.documents.length - 1; i >= 0; i--) {
                var currentDoc = app.documents[i];
                for (var j = 0; j < config.close.length; j++) if (key(info(currentDoc)) === new File(config.close[j]).fsName.toLowerCase())
                    currentDoc.close(SaveOptions.DONOTSAVECHANGES);
            }
            setPngPreferences(config.restore_preferences);
            result = {documents: documents(), png_preferences: pngPreferences()};
            assertProtected(result.documents);
        } else throw new Error('Unknown observer phase');
    } catch (error) {
        result = {error: String(error), line: error.line, stack: $.stack};
    } finally {
        if (doc !== null) doc.close(SaveOptions.DONOTSAVECHANGES);
        log.encoding = 'UTF-8';
        if (!log.open('w')) throw new Error('Cannot write observer result');
        log.write(encode(result));
        log.close();
    }
}());
