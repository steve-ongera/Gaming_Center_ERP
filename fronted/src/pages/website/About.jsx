import { BsTools } from 'react-icons/bs'

export default function About() {
    return (
        <div className='container py-5 text-center'>
            <BsTools size={70} className='text-primary mb-3' />
            <h2>About</h2>
            <p className='text-muted'>This page is currently under development.</p>
        </div>
    )
}
