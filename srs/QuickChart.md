Introduction
QuickChart is a web service that generates chart images on-the-fly. These images are suitable for embedding in email, SMS, chatbots, and other formats. Charts are rendered by Chart.js, a popular open-source charting library.

Getting started
QuickChart works by taking Chart.js configurations and rendering them as images. You may send your chart configuration in JSON or Javascript format using a simple URL or through POST request.

For example, take this simple Chart.js configuration:

{
  type: 'bar',                                // Show a bar chart
  data: {
    labels: [2012, 2013, 2014, 2015, 2016],   // Set X-axis labels
    datasets: [{
      label: 'Users',                         // Create the 'Users' dataset
      data: [120, 60, 50, 180, 120]           // Add data to the chart
    }]
  }
}

We'll pack the Chart.js object into the /chart URL endpoint:

https://quickchart.io/chart?c={type:'bar',data:{labels:[2012,2013,2014,2015, 2016],datasets:[{label:'Users',data:[120,60,50,180,120]}]}}
The URL generates this chart image, a rendering of the Chart.js config above:

A basic chart configuration rendered by QuickChart
Edit this example

Try making adjustments to the example above!

Edit the chart and replacing bar with line or pie to get a different type of chart.
Change the legend labels.
Add another dataset to get a grouped bar chart.
Because QuickChart is built on open-source chart libraries, our charts are flexible and highly customizable. Keep on reading to learn more or view more chart examples.

Using the API
The https://quickchart.io/chart endpoint supports both GET and POST methods. These parameters provide control over dimensions, resolution, background, and Chart.js version of your chart:

Parameter	Type	Description
chart	string	Chart.js configuration object to render. This is the definition of the chart in Javascript or JSON format.
width	integer	Width of image in pixels. Defaults to 500
height	integer	Height of image in pixels. Defaults to 300
devicePixelRatio	integer	Device pixel ratio of output. Set to 1 for normal resolution, 2 for retina. Defaults to 2
backgroundColor	string	RGB, HEX, HSL, or color name. Defaults to transparent
version	string	Chart.js version. Default to 2. Setting to 4 enables latest stable Chart.js v4 support.
format	string	png, webp, svg, or pdf. Defaults to png
encoding	string	url or base64. Defaults to url
info
Learn more about API parameters and the POST endpoint.

Customization
Because QuickChart is built on the open-source Chart.js library, charts are flexible and highly customizable. To learn more, view our examples gallery or see the reference section to learn how to use Chart.js.

1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
⌄
⌄
⌄
⌄
⌄
⌄
⌄
⌄
{
  type: 'bar',
  data: {
    labels: ['January', 'February', 'March', 'April', 'May', 'June', 'July'],
    datasets: [
      {
        type: 'line',
        label: 'Dataset 1',
        borderColor: 'rgb(54, 162, 235)',
        borderWidth: 2,
        fill: false,
        data: [-33, 26, 29, 89, -41, 70, -84],
      },
      {
        label: 'Dataset 2',
        backgroundColor: 'rgb(255, 99, 132)',
        data: [-42, 73, -69, -94, -81, 18, 87],
        borderColor: 'white',
        borderWidth: 2,
      },
      {
        label: 'Dataset 3',
        backgroundColor: 'rgb(75, 192, 192)',
        data: [93, 60, -15, 77, -59, 82, -44],
      },
    ],
  },
  options: {
    title: {
      display: true,
      text: 'My chart',
    },
  },
}
Chart URL: https://quickchart.io/chart?c={ type: 'bar', data: { labels: ['January', 'February', 'March', 'April', 'May', 'June', 'July'], datasets: [ { type...
A more complex chart example with 3 data series and multiple series types
Open in full editor

API parameters
The chart endpoint https://quickchart.io/chart accepts query parameters listed below.

Combine these parameters in your query string. For example:

https://quickchart.io/chart?width=500&height=300&chart={...}
If you prefer not to construct the URL yourself, client libraries are available in many programming languages.

Supported parameters
chart
Type: Javascript or JSON object
Required: yes
Parameter name: chart or c
Chart.js configuration object to render. This is the definition of the chart in Javascript or JSON format.

If you are sending a GET request, we recommend that you URL-encode your chart configuration. If not encoded, you will run into problems with special characters or syntax errors in your program. You may also use base64 encoding (see encoding).

width
Type: integer
Default: 500
Parameter name: width or w
Width of the image in pixels.

height
Type: integer
Default: 300
Parameter name: height or h
Height of the image in pixels.

devicePixelRatio
Type: integer
Accepted values: 1 or 2
Default: 2
Device pixel ratio of the output. Image width and height are multiplied by this value. Defaults to 2.0 to ensure best image support on Retina devices.

info
This setting defaults to 2, meaning all images will be 2x width and height! To get an image that is exactly width*height, set devicePixelRatio to 1.

backgroundColor
Type: string
Accepted values: rgb, hex, hsl, color names
Default: transparent
Parameter name: backgroundColor or bkg
Background of the chart canvas. Accepts rgb format (rgb(255,255,120)), colors (red), and URL-encoded hex values (%23ff00ff).

version
Type: string
Accepted values: 2, 3, 4, or any valid Chart.js version string
Default: 2.9.4
Parameter name: version or v
Chart.js version. Setting version to 4 enables latest stable Chart.js v4 support. Defaults to latest version of Chart.js v2.

format
Type: string
Accepted values: png, webp, jpg, svg, pdf, base64
Default: png
Parameter name: format or f
Format of your output.

encoding
Type: string
Accepted values: url or base64
Default: url
Encoding of your chart parameter.

Postman examples
We've put together a public Postman collection for the QuickChart API. View it here:


POST endpoint
If your chart is large or complicated, you may prefer to send a POST request rather than a GET request. This avoids limitations on URL length and means you don't have to worry about URL encoding. The /chart POST endpoint returns a chart. It takes the standard request parameters as a JSON object:

{
  "version": "2",
  "backgroundColor": "transparent",
  "width": 500,
  "height": 300,
  "devicePixelRatio": 1.0,
  "format": "png",
  "chart": {...}
}

tip
To include Javascript code in chart (e.g. to format labels), you must send chart as a string, not as a JSON object.

For examples of this, see documentation on using JS Functions.

Here is the type specification of the POST data object:

{
  width: string;                        // Pixel width
  height: string;                       // Pixel height
  devicePixelRatio: number;             // Pixel ratio (2.0 by default)
  format: string;                       // png, svg, or webp
  backgroundColor: string;              // Canvas background
  version: string;                      // Chart.js version
  key: string;                          // API key (optional)
  chart: string | ChartConfiguration;   // Chart.js configuration
}

ChartConfiguration is a Chart.js v2+ configuration object in JSON format.

Advanced API
Short URLs
You may want to create a shorter URL for your charts, especially if you are sending them via email or SMS. To generate a short URL for your chart, send a POST request to https://quickchart.io/chart/create.

The endpoint takes the following JSON request body, identical to the /chart POST endpoint:

{
  width: string;                        // Pixel width
  height: string;                       // Pixel height
  devicePixelRatio: number;             // Pixel ratio (2.0 by default)
  format: string;                       // png, svg, or webp
  backgroundColor: string;              // Canvas background
  version: string;                      // Chart.js version
  key: string;                          // API key (optional)
  chart: string | ChartConfiguration;   // Chart.js configuration
}

Here's an example using curl. You can use any library that sends an HTTP POST request:

curl -X POST \
     -H 'Content-Type: application/json' \
     -d '{"chart": {"type": "bar", "data": {"labels": ["Hello", "World"], "datasets": [{"label": "Foo", "data": [1, 2]}]}}}' \
     https://quickchart.io/chart/create


Here's an equivalent request using Python:

import json
import requests

quickchart_url = 'https://quickchart.io/chart/create'
post_data = {'chart': {'type': 'bar', 'data': {'labels': ['Hello', 'World'],
             'datasets': [{'label': 'Foo', 'data': [1, 2]}]}}}

response = requests.post(
    quickchart_url,
    json=post_data,
)

if (response.status_code != 200):
    print('Error:', response.text)
else:
    chart_response = json.loads(response.text)
    print(chart_response)

You will get a response that looks like this:

{
  "success": true,
  "url": "https://quickchart.io/chart/render/9a560ba4-ab71-4d1e-89ea-ce4741e9d232"
}

Go to the URL in the response to render your chart.

Please note the following limitations:

It can take a couple seconds for short URLs to become active globally.
Request inputs are not validated before the URL is created. The chart is only rendered when the URL is visited.
If your chart includes Javascript, you must supply your chart definition as a string (see using JS functions).
Saved charts expire after 3 days for free users, 6 months for paid users.
Templates
If you want to generate many charts, but they only differ slightly, you may prefer to use chart templates. Any chart with a Short URL can also be used as a template.

Customize a template by adding URL parameters to the template URL. The following template parameters are supported:

title - The title of the chart
labels - Comma-separated labels for the label axis of a chart (usually the X axis)
data1, data2, ..., dataN - Comma-separated data values for each dataseries
label1, label2, ..., labelN - Comma-separated labels for each dataseries
backgroundColor1, ..., backgroundColorN - Comma-separated backgrounds for each dataseries
borderColor1, ..., borderColorN - Comma-separated border colors for each dataseries
For example, this URL will take template zf-abc-123 and update its title to "New title":

https://quickchart.io/chart/render/zf-abc-123?title=New title
We can add a labels URL parameter:

https://quickchart.io/chart/render/zf-abc-123?title=New title&labels=Q1,Q2,Q3,Q4
Or even override multiple datasets:

https://quickchart.io/chart/render/zf-abc-123?data1=40,60,80,100&data2=5,6,7,8
In addition to plain numbers, templates also accept (x, y) data values and arbitrary JSON objects.

An example walkthrough with a live template can be viewed here.

IFrames
By default, short URLs/templates render as images and are not interactive. If you'd like to display a chart with interactive tooltips in an iframe, take the unique portion of the shortened URL and append it to the /chart-maker/view/ endpoint.

For example, given the short URL:

https://quickchart.io/chart/render/9a560ba4-ab71-4d1e-89ea-ce4741e9d232

Here is the corresponding iframe URL:

https://quickchart.io/chart-maker/view/9a560ba4-ab71-4d1e-89ea-ce4741e9d232

You can embed it like a regular iframe. Be sure to set a frame width and height that is compatible with your chart. Here's an HTML example:

<iframe src="demo_iframe.htm" frameborder="0" height="500" width="300" title="Iframe Example"></iframe>

Expiration
Expiration of short URLs and templates varies based on whether you've created them using the /chart/create API endpoint, or via the Chart Maker.

Free Tier	Professional Plan
API	3 days	6 months
Can be extended by contacting support
Advanced Chart Editor (Sandbox)	3 days	6 months
Can be extended by contacting support
Chart Maker	60+ days
Expiration is reset when rendered	6+ months
Expiration is reset when rendered
An expired short URL will return a 404 Not Found error.