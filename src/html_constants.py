HTML_STYLE = """
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<link type="text/css" rel="stylesheet" href="resources/sheet.css">
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<link type="text/css" rel="stylesheet" href="resources/sheet.css">
<style type="text/css">
    .ritz .waffle a {
        color: inherit;
    }
    .ritz .waffle .s0 {
        text-align: center;
        color: #000000;
        font-family: 'Arial';
        font-size: 10pt;
        vertical-align: bottom;
        white-space: nowrap;
        direction: ltr;
        padding: 2px 3px 2px 3px;
    }
    .grid-container {
        height: 100;
        width: 100;
        overflow: auto;
    }
    .grid-container {
        background-color: #eee;
        overflow: hidden;
        position: relative;
        z-index: 0;
    }
    div[Attributes Style] {
        direction: ltr;
        unicode-bidi: isolate;
    }
    user agent stylesheet
    div {
        display: block;
    }
    body {
        color: black;
        font-weight: normal;
        font-size: 13px;
        font-family: Roboto,RobotoDraft,Helvetica,Arial,sans-serif;
        margin: 0;
    }
    .one {
        background-color: #eee
    }
    .two {
        background-color: White
    }
</style>
"""

HTML_TABLE = """
<div class="ritz grid-container" dir="ltr">
    <table class="waffle" cellspacing="0" cellpadding="0">
        <thead>
            <tr>
                %s
            </tr>
        </thead>
        <tbody>
            %s
        </tbody>
    </table>
</div>
"""

HTML_HEADER = """
<th id="1115023821C0" style="width:100px;" class="column-headers-background">{0}</th>
<th id="1115023821C1" style="width:100px;" class="column-headers-background">{1}</th>
<th id="1115023821C2" style="width:100px;" class="column-headers-background">{2}</th>
"""

HTML_ROW = """
<tr style="height: 20px">
    <td class="s0 {3}" dir="ltr">{0}</td>
    <td class="s0 {3}" dir="ltr">{1}</td>
    <td class="s0 {3}" dir="ltr">{2}</td>
</tr>
"""

HTML_HREF = "<a href=\"{0}\" target=\"_blank\" rel=\"noopener noreferrer\">Click Me!</a>"