import * as THREE from 'three';
import {OrbitControls} from '/vendor/controls/OrbitControls.js';
import {GLTFLoader} from '/vendor/loaders/GLTFLoader.js';

export class MeshViewer {
  constructor(canvas){
    this.canvas=canvas;this.renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));this.scene=new THREE.Scene();
    this.camera=new THREE.PerspectiveCamera(35,1,.01,1000);this.camera.position.set(3,2,3);
    this.controls=new OrbitControls(this.camera,canvas);this.controls.enableDamping=true;
    this.scene.add(new THREE.HemisphereLight(0xffffff,0x76856a,3));
    const key=new THREE.DirectionalLight(0xffffff,3);key.position.set(3,6,4);this.scene.add(key);
    this.group=new THREE.Group();this.scene.add(this.group);this.serial=0;this.wireframe=false;
    new ResizeObserver(()=>this.resize()).observe(canvas.parentElement);
    this.renderer.setAnimationLoop(()=>{if(!canvas.hidden){this.controls.update();this.renderer.render(this.scene,this.camera);}});
  }
  resize(){const rect=this.canvas.parentElement.getBoundingClientRect();this.renderer.setSize(rect.width,Math.max(rect.height,300),false);this.camera.aspect=rect.width/Math.max(rect.height,300);this.camera.updateProjectionMatrix();}
  dispose(object){object.traverse(node=>{if(node.isMesh){node.geometry.dispose();for(const material of Array.isArray(node.material)?node.material:[node.material])material.dispose();}});}
  clear(){this.serial++;for(const child of [...this.group.children]){this.dispose(child);this.group.remove(child);}}
  async load(url){this.clear();const serial=this.serial;const gltf=await new GLTFLoader().loadAsync(url);if(serial!==this.serial){this.dispose(gltf.scene);return;}
    gltf.scene.traverse(node=>{if(node.isMesh){for(const material of Array.isArray(node.material)?node.material:[node.material])material.dispose();node.material=new THREE.MeshStandardMaterial({color:0xb6c4a8,roughness:.78,metalness:.02,side:THREE.DoubleSide,wireframe:this.wireframe});}});
    this.group.add(gltf.scene);const box=new THREE.Box3().setFromObject(gltf.scene);const center=box.getCenter(new THREE.Vector3());const size=box.getSize(new THREE.Vector3());const span=Math.max(size.x,size.y,size.z);
    this.camera.position.copy(center).add(new THREE.Vector3(1,.6,1.8).normalize().multiplyScalar(span*2.3));this.camera.near=span/1000;this.camera.far=span*100;this.camera.updateProjectionMatrix();this.controls.target.copy(center);this.controls.minDistance=span*.2;this.controls.maxDistance=span*10;this.controls.update();this.resize();
  }
  toggleWireframe(){this.wireframe=!this.wireframe;this.group.traverse(node=>{if(node.isMesh)node.material.wireframe=this.wireframe;});return this.wireframe;}
}
