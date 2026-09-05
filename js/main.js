/* ==================================================
   FAITH ASSEMBLY CHURCH MUGUGA
   MAIN JAVASCRIPT
================================================== */


/* ==================================================
   PAGE LOADER
================================================== */

window.addEventListener("load", function () {

    const loader =
        document.getElementById("pageLoader");

    if (loader) {

        setTimeout(function () {

            loader.classList.add("hidden");

        }, 500);

    }

});



/* ==================================================
   MOBILE MENU
================================================== */

const menuToggle =
    document.getElementById("menuToggle");

const navLinks =
    document.getElementById("navLinks");


if (menuToggle && navLinks) {

    menuToggle.addEventListener(
        "click",
        function () {

            navLinks.classList.toggle("show");

        }
    );


    /* CLOSE MENU WHEN LINK IS CLICKED */

    const links =
        navLinks.querySelectorAll("a");


    links.forEach(function (link) {

        link.addEventListener(
            "click",
            function () {

                navLinks.classList.remove("show");

            }
        );

    });

}



/* ==================================================
   SCROLL REVEAL ANIMATION
================================================== */

const revealElements =
    document.querySelectorAll(".reveal");


const revealObserver =
    new IntersectionObserver(
        function (entries) {

            entries.forEach(function (entry) {

                if (entry.isIntersecting) {

                    entry.target.classList.add("active");

                    revealObserver.unobserve(
                        entry.target
                    );

                }

            });

        },
        {
            threshold: 0.12
        }
    );


revealElements.forEach(function (element) {

    revealObserver.observe(element);

});



/* ==================================================
   ACTIVE NAVIGATION
================================================== */

const sections =
    document.querySelectorAll("section[id]");

const navigationLinks =
    document.querySelectorAll(
        ".nav-links a"
    );


window.addEventListener(
    "scroll",
    function () {

        let currentSection = "";

        sections.forEach(function (section) {

            const sectionTop =
                section.offsetTop - 120;

            const sectionHeight =
                section.offsetHeight;

            if (
                window.scrollY >= sectionTop &&
                window.scrollY < sectionTop + sectionHeight
            ) {

                currentSection =
                    section.getAttribute("id");

            }

        });


        navigationLinks.forEach(
            function (link) {

                link.classList.remove("active");

                if (
                    link.getAttribute("href") ===
                    "#" + currentSection
                ) {

                    link.classList.add("active");

                }

            }
        );

    }
);
/* ==========================================
   M-PESA GIVING COPY BUTTONS
========================================== */

function copyGivingNumber(number, button) {

    navigator.clipboard.writeText(number)
        .then(function () {

            const originalText = button.textContent;

            button.textContent = "COPIED ✓";

            setTimeout(function () {

                button.textContent = originalText;

            }, 2000);

        })
        .catch(function () {

            alert("Copy failed. Please copy the number manually: " + number);

        });

}