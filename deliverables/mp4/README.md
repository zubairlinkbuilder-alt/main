# Beginners article: GIF → MP4 swap

Page: https://exercisemenu.com/exercises-with-a-medicine-ball-for-beginners/

| Section | Old GIF | New MP4 |
|---|---|---|
| 1. Medicine Ball Slam | 8.0 MB | `medicine-ball-slam.mp4` 1.3 MB |
| 2. Medicine Ball Overhead Press | 7.3 MB | `medicine-ball-overhead-press.mp4` 1.2 MB |
| 5. Russian twist | 7.6 MB | `medicine-ball-russian-twist.mp4` 1.1 MB |

## Steps

1. Upload the three `.mp4` files and the three `-poster.jpg` files to the Media Library.
2. In the article, delete the old GIF image block in each section.
3. Add a **Custom HTML** block in its place with this code, changing the two URLs to the
   ones WordPress gives the uploaded files:

```html
<video src="https://exercisemenu.com/wp-content/uploads/2026/10/medicine-ball-slam.mp4"
       poster="https://exercisemenu.com/wp-content/uploads/2026/10/medicine-ball-slam-poster.jpg"
       autoplay loop muted playsinline preload="metadata"
       width="270" height="480"
       aria-label="Medicine ball slam exercise demonstration"></video>
```

`autoplay loop muted playsinline` makes it play like a GIF on phones too. Keep the old
alt text as the `aria-label`.
