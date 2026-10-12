// Desktop cleanup regression fixture: show Illustrator's real Color Picker without modifying document appearance.
var closed = false;
try {
    var color = new RGBColor();
    color.red = 0; color.green = 174; color.blue = 239;
    app.showColorPicker(color);
    closed = true;
} catch (error) {
    var crash = new File(config.result + '.crash.txt');
    crash.encoding = 'UTF-8';
    if (!crash.open('w')) throw new Error('Cannot record Color Picker fixture failure');
    crash.write(String(error) + '\n' + $.stack);
    crash.close();
}
var result = new File(config.result);
result.encoding = 'UTF-8';
if (!result.open('w')) throw new Error('Cannot record Color Picker fixture result');
result.write('{"closed":' + (closed ? 'true' : 'false') + '}');
result.close();
