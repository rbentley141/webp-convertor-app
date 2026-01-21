import { useState, type ChangeEvent, type FormEvent } from 'react'

import '../App.css'

type UploadProps = {
  onSubmit: (file: File) => void | Promise<void>;
};

export default function Upload({ onSubmit }: UploadProps){
    const [file, setFile] = useState<File | null>(null);
    const [isUploading, setIsUploading] = useState<boolean>(false);

    function handleChange(e: ChangeEvent<HTMLInputElement>){
        setFile(e.target.files?.[0] ?? null)
    }

    async function handleSubmit(e: FormEvent<HTMLFormElement>){
        e.preventDefault();
        if (!file || isUploading) return;
        
        setIsUploading(true);
        try {
            await onSubmit(file);
        } finally {
            setIsUploading(false);
        }
    }

    return (
        <form onSubmit={handleSubmit} className="upload-form">
            <label htmlFor="fileInput">
                Upload .jpg, .png, .jpeg, or .zip.
            </label>
            <input
                id="fileInput"
                name="file"
                type="file"
                accept=".zip,.jpg,.jpeg,.png"
                onChange={handleChange}
            /> 
            <button type="submit" disabled={!file || isUploading}>
                {isUploading ? 'Uploading...' : 'Upload'}
            </button>
        </form>
    );
}