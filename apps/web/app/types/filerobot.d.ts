declare module 'filerobot-image-editor' {
  interface EditedImage { imageCanvas?: HTMLCanvasElement; imageBase64?: string }
  export default class FilerobotImageEditor {
    constructor(container: HTMLElement, config: Record<string, unknown>)
    render(config?: Record<string, unknown>): void
    terminate(): void
    getCurrentImgData(info?: Record<string, unknown>, pixelRatio?: number): { imageData?: EditedImage }
  }
}
