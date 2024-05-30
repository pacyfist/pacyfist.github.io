---
tags: ["javascript", "typescript", "node", "three.js"]
categories: ["javascript", "three.js"]
title: "Playing with Node.js and Three.js: From Nothing to Your First 3D Web Project in 15 Minutes"
image:
  path: /assets/img/2024-05-30/cube.png
  alt: It's super easy to add 3D Object onto your website!
---
During my university days, I became fascinated with 3D graphics, a challenging field at the time due to its complex mathematics and scarce literature on the subject. Unfortunately insanely expensive software accessible only through the university successfully stood in my way of mastering that field. Today, however, creating 3D objects has become remarkably accessible, with the ability to render anything in a browser spending under 15 minutes.

## Setup the Environment

Let's make a folder for our project.

```console
mkdir whatever
cd ./whatever
```

Now we and initialize a new node project. That little `-y` is there to avoid answering annoying questions.

```console
npm init -y
```

We'll be using Three.js so let's install it now.

```console
npm install three
```

For completely no reason my favorite bundler is `parcel` so let's install it as dev dependency. 

```console
npm install --save-dev parcel
```
Those steps gave us an almost ready `package.json` file.

```json
{
  "name": "whatever",
  "version": "1.0.0",
  "description": "",
  "main": "index.js",
  "scripts": {
    "test": "echo \"Error: no test specified\" && exit 1"
  },
  "keywords": [],
  "author": "",
  "license": "ISC",
  "devDependencies": {
    "parcel": "^2.12.0"
  },
  "dependencies": {
    "three": "^0.164.1"
  }
}
```
It just need a little tweaking to allow parcel to do it's magic.

```json
{
  "name": "whatever",
  "version": "1.0.0",
  "description": "",
  "scripts": {
    "start": "parcel src/index.html", 
    "build": "parcel build src/index.html"
  },
  "keywords": [],
  "author": "",
  "license": "ISC",
  "devDependencies": {
    "parcel": "^2.12.0"
  },
  "dependencies": {
    "three": "^0.164.1"
  }
}
```

## Project Code

Now we just need to create two files where we put the actual project.

 `./src/index.html`
```html
<!doctype html>
<html>

<head>
  <style>
    * {
      margin: 0;
      padding: 0;
    }
  </style>
  <script type="module" src="./index.js"></script>
</head>

<body>
</body>

</html>
```

`./src/index.js`
```javascript
import * as THREE from 'three';

// Create a scene
const scene = new THREE.Scene();

// Create a camera
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.z = 5;

// Create a cube
const geometry = new THREE.BoxGeometry(1, 1, 1);
const material = new THREE.MeshMatcapMaterial({ color: 0x00ff00 });
const cube = new THREE.Mesh(geometry, material);
scene.add(cube);

// Create a renderer
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);

// Setup renderer magic
renderer.setPixelRatio(window.devicePixelRatio);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1;

// Add the renderer to the DOM
document.body.appendChild(renderer.domElement);

renderer.setAnimationLoop(animate);

// Animation loop
function animate(timestamp) {

    // Rotate the cube
    cube.rotation.x += 0.01;
    cube.rotation.y += 0.015;

    // Render the scene
    renderer.render(scene, camera);
}

// Resize the canvas when the window is resized
window.addEventListener('resize', (event) => {
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
});

```
## Running the project

This is a way to run the project that will automatically reload the page if it detects that you changed any file in the source code.

```console
npm start
```

Now go to `http://localhost:1234/` (or other address displayed in your console) and you end up with a green rotating 3D cube.

<iframe src="/assets/show/2024-05-30/cube.html" width="100%" height="500px"></iframe>

## Building the project

We can easily compile this project into static, minimized files that are ready for publishing.

First, run the following command:

```console
npm run build
```

After running this command, you'll find a new dist folder in your project directory. This folder contains everything you need:

- ./dist/index.2aec1ae7.js
- ./dist/index.2aec1ae7.js.map
- ./dist/index.html

You can ignore the .js.map files as they are only useful for debugging. To publish your project, you only need the other two files. All the necessary JavaScript libraries have been bundled together and minimized to ensure the fastest possible loading time.