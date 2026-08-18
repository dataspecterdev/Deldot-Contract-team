// Type augmentations for the File System Access API (webkitGetAsEntry)
interface FileSystemEntry {
  isFile: boolean
  isDirectory: boolean
  name: string
}

interface FileSystemFileEntry extends FileSystemEntry {
  file(successCallback: (file: File) => void, errorCallback?: (err: DOMException) => void): void
}

interface FileSystemDirectoryEntry extends FileSystemEntry {
  createReader(): FileSystemDirectoryReader
}

interface FileSystemDirectoryReader {
  readEntries(
    successCallback: (entries: FileSystemEntry[]) => void,
    errorCallback?: (err: DOMException) => void
  ): void
}

interface DataTransferItem {
  webkitGetAsEntry?(): FileSystemEntry | null
}
