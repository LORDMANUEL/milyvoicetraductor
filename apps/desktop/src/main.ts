import { mount } from 'svelte';
import App from './App.svelte';
import '../../../packages/brand/tokens.css';
import './styles/global.css';

const target = document.getElementById('app');
if (!target) throw new Error('No se encontró el nodo raíz de MilyVoiceTraductor.');
mount(App, { target });
